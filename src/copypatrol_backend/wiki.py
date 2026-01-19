from __future__ import annotations

from typing import TYPE_CHECKING

import pywikibot
import pywikibot.exceptions
from pywikibot.page import Revision

if TYPE_CHECKING:
    from pywikibot.site import APISite


def load_revisions(
    site: APISite,
    revids: list[int],
    /,
    *,
    content: bool = False,
) -> dict[int, Revision] | None:
    rvprops = [
        "ids",
        "flags",
        "timestamp",
        "user",
        "userid",
        "size",
        "sha1",
        "contentmodel",
        "comment",
        "tags",
        "roles",
    ]
    if content:
        rvprops.append("content")
    data = site.simple_request(
        action="query",
        revids=revids,
        prop="revisions",
        rvprop=rvprops,
        rvslots="*",
    ).submit()
    if "badrevids" in data["query"]:
        return None
    return {
        rev["revid"]: Revision(
            pageid=page["pageid"],
            ns=page["ns"],
            title=page["title"],
            **rev,
        )
        for page in data["query"]["pages"].values()
        for rev in page["revisions"]
    }


def submit_pagetriage(site: APISite, page_id: int, rev_id: int, /) -> None:
    if not site.has_extension("PageTriage"):
        raise pywikibot.exceptions.UnknownExtension(  # pragma: no cover
            f"PageTriage is not enabled on {site!r}"
        )
    if not site.has_right("pagetriage-copyvio"):
        raise pywikibot.exceptions.UserRightsError(  # pragma: no cover
            f"{site.username()} does not have the required pagetriage-copyvio"
            " user right"
        )
    data = site.simple_request(
        action="pagetriagelist",
        page_id=page_id,
        formatversion="2",
    ).submit()
    if page_id in data["pagetriagelist"]["pages_missing_metadata"]:
        return
    try:
        site.simple_request(
            action="pagetriagetagcopyvio",
            revid=rev_id,
            token=site.tokens["csrf"],
            formatversion="2",
        ).submit()
    except pywikibot.exceptions.APIError:  # pragma: no cover
        pywikibot.log(data)
        pywikibot.exception()
        pywikibot.error(f"failed to add {rev_id=} to PageTriage")
    else:
        pywikibot.debug(f"{rev_id=} added to PageTriage")
