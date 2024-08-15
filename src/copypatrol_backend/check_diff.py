from __future__ import annotations

import difflib
import re
from contextlib import suppress
from functools import cache
from typing import TYPE_CHECKING

import mwparserfromhell
import pywikibot
import pywikibot.exceptions
from pywikibot.page import Revision
from pywikibot_extensions.page import Page

from copypatrol_backend.wiki import load_revisions


if TYPE_CHECKING:
    from pywikibot.site import APISite


@cache
def category_regex(site: APISite, /) -> re.Pattern[str]:
    namespaces = "|".join(site.namespaces.CATEGORY)
    return re.compile(
        rf"\[\[\s*:?\s*({namespaces})\s*:[^\]]+?\]\]\s*",
        flags=re.I,
    )


@cache
def file_name_regex(site: APISite, /) -> re.Pattern[str]:
    namespaces = "|".join(site.namespaces.FILE)
    extensions = "|".join(site.file_extensions)
    return re.compile(rf"({namespaces})\s*:.+?\.({extensions})", flags=re.I)


def clean_wikitext(text: str, /, *, site: APISite) -> str:
    text = text.strip()
    if not text:
        return ""

    # remove bold/italic wikitext markup
    text = re.sub(r"(?P<open>'{2,3})(.+?)(?P=open)", r"\2", text)

    # remove categories
    text = category_regex(site).sub("", text)

    # remove quotes of less than 50 words
    for quote in re.findall('["“«].+?["”»]', text):
        if len(quote.split()) < 50:
            text = text.replace(quote, "")

    wikicode = mwparserfromhell.parse(text, skip_style_tags=True)
    # replace external links with their title
    for link in wikicode.ifilter_external_links():
        with suppress(ValueError):
            wikicode.replace(link, link.title or "")
    # remove block quotes and references of less than 50 words
    for tag in wikicode.ifilter_tags(
        matches=lambda x: x.tag.lower() in ("blockquote", "ref", "references"),
    ):
        contents = tag.contents.strip_code(keep_template_params=True).strip()
        if len(contents.split(" ")) < 50:
            with suppress(ValueError):
                wikicode.remove(tag)
    # strip remaining code
    text = wikicode.strip_code(keep_template_params=True)

    # remove file names
    text = file_name_regex(site).sub("", text)

    # normalize whitespace
    text = re.sub(r" {2,}", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"( ?\n){3,}", r"\n\n", text)

    return text.strip()


def added_revision_text(old: str, new: str, /, *, site: APISite) -> str:
    old = clean_wikitext(old, site=site)
    new = clean_wikitext(new, site=site)
    sm = difflib.SequenceMatcher(None, old, new)
    return "\n".join(
        line
        for op, _, _, new_start, new_end in sm.get_opcodes()
        if op == "insert"
        if new_end - new_start > 50
        for line in "".join(new[new_start:new_end]).strip(" ").splitlines()
        if not line.strip() or line.strip() not in old
    ).strip()


def check_diff(
    page: pywikibot.Page,
    old: int,
    new: int,
    /,
) -> str | None:
    def rev_text_hidden(rev: Revision) -> bool:
        if "texthidden" in rev["slots"]["main"]:
            pywikibot.debug(f"revision {rev.revid} to {page!r} is hidden")
            return True
        return False

    def small_len(text: str) -> bool:
        if len(text) < 500:
            pywikibot.debug(f"revision {new} to {page!r} too small to compare")
            return True
        return False

    pywikibot.debug(f"checking revision {new} to {page!r}")
    revs = load_revisions(
        page.site,
        [r for r in (old, new) if r > 0],
        content=True,
    )
    if revs is None:
        pywikibot.debug(f"{page!r} was deleted")
        return None
    new_rev = revs[new]
    if "mw-rollback" in new_rev.tags or {"mw-undo", "twinkle"} <= set(
        new_rev.tags
    ):
        pywikibot.debug(f"revision {new} to {page!r} was a rollback")
        return None
    if rev_text_hidden(new_rev) or small_len(new_rev.text):
        return None
    if old > 0:
        old_rev = revs[old]
        if rev_text_hidden(old_rev):
            return None
        added_text = added_revision_text(
            old_rev.text,
            new_rev.text,
            site=page.site,
        )
    else:
        added_text = clean_wikitext(new_rev.text, site=page.site)
    if small_len(added_text):
        return None
    # remove text possibly copied from pages linked in the comment
    if not new_rev.commenthidden and new_rev.comment:
        comment_wikicode = mwparserfromhell.parse(
            new_rev.comment,
            skip_style_tags=True,
        )
        for wikilink in comment_wikicode.ifilter_wikilinks():
            with suppress(
                ValueError,
                pywikibot.exceptions.InconsistentTitleError,
                pywikibot.exceptions.InvalidPageError,
                pywikibot.exceptions.InvalidTitleError,
            ):
                linked_page = Page.from_wikilink(wikilink, page.site)
                if linked_page.namespace().id < 0 or not linked_page.exists():
                    continue
                for rev in linked_page.revisions(total=2, content=True):
                    if rev_text_hidden(rev):
                        continue
                    linked_page_text = clean_wikitext(rev.text, site=page.site)
                    added_text = "\n".join(
                        part
                        for part in added_text.splitlines()
                        if not part.strip() or part not in linked_page_text
                    )
        if small_len(added_text):
            return None
    return added_text
