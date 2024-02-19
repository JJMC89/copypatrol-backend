from __future__ import annotations

import re

import pytest
import pywikibot
from pywikibot.page import Revision

from copypatrol_backend import check_diff
from testing.resources import resource


SITE = pywikibot.Site("en", "wikipedia")


@pytest.fixture
def mock_filename_regex(mocker):
    regex = re.compile(r"(File|Image)\s*:.+?\.(png|gif|jpg|jpeg)", flags=re.I)
    mocker.patch(
        "copypatrol_backend.check_diff.file_name_regex",
        return_value=regex,
    )
    yield


def test_category_regex():
    expected = r"\[\[\s*:?\s*(Category)\s*:[^\]]+?\]\]\s*"
    assert check_diff.category_regex(SITE).pattern == expected


def test_file_name_regex(mocker):
    mocker.patch(
        "copypatrol_backend.check_diff.pywikibot.site.APISite.siteinfo",
        new_callable=mocker.PropertyMock,
        return_value={
            "fileextensions": [
                {"ext": ext} for ext in ["png", "gif", "jpg", "jpeg"]
            ]
        },
    )
    expected = r"(File|Image)\s*:.+?\.(gif|jpeg|jpg|png)"
    assert check_diff.file_name_regex(SITE).pattern == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param(
            resource("Kommet,_ihr_Hirten-1126962296.txt"),
            resource("Kommet,_ihr_Hirten-1126962296-cleaned.txt").strip(),
            id="short refs",
        ),
        pytest.param(
            resource("Basil_Lee_Whitener-1173291523.txt"),
            resource("Basil_Lee_Whitener-1173291523-cleaned.txt").strip(),
            id="long ref",
        ),
    ],
)
def test_clean_wikitext(mock_filename_regex, text, expected):
    assert check_diff.clean_wikitext(text, site=SITE) == expected


def test_clean_wikitext_empty():
    assert check_diff.clean_wikitext("", site=SITE) == ""


def test_added_revision_text(mock_filename_regex):
    old = resource("Kommet,_ihr_Hirten-1125722395.txt")
    new = resource("Kommet,_ihr_Hirten-1126962296.txt")
    expected = resource("Kommet,_ihr_Hirten-1126962296-added.txt").strip()
    assert check_diff.added_revision_text(old, new, site=SITE) == expected


@pytest.mark.parametrize(
    "old_text, new_text, new_comment, new_tags, added_text",
    [
        pytest.param(
            resource("Kommet,_ihr_Hirten-1125722395.txt"),
            resource("Kommet,_ihr_Hirten-1126962296.txt"),
            "another edit summary",
            [],
            resource("Kommet,_ihr_Hirten-1126962296-added.txt").strip(),
            id="Kommet",
        ),
        pytest.param(
            "foo bar" * 100,
            "small" * 50,
            "another edit summary",
            [],
            None,
            id="small addition 1",
        ),
        pytest.param(
            "foo bar" * 100,
            f'{"baz " * 70} "{"small " * 40}"',
            "another edit summary",
            [],
            None,
            id="small addition 2",
        ),
        pytest.param(
            "foo bar" * 100,
            f'{"baz" * 500} "short quote"',
            "another edit summary",
            [],
            "baz" * 500,
            id="short quote",
        ),
        pytest.param(
            "foo bar" * 100,
            f'"{"baz " * 500}"',
            "another edit summary",
            [],
            f'"{"baz " * 500}"',
            id="long quote",
        ),
        pytest.param(
            "foo bar" * 100,
            "baz" * 500,
            "another edit summary",
            ["mw-rollback"],
            None,
            id="mw-rollback",
        ),
        pytest.param(
            "foo bar" * 100,
            "baz" * 500,
            "another edit summary",
            ["mw-rollback", "foo"],
            None,
            id="mw-rollback foo",
        ),
        pytest.param(
            "foo bar" * 100,
            "baz" * 500,
            "another edit summary",
            ["mw-undo", "twinkle"],
            None,
            id="mw-undo twinkle",
        ),
        pytest.param(
            "foo bar" * 100,
            "baz" * 500,
            "another edit summary",
            ["mw-undo", "twinkle", "foo"],
            None,
            id="mw-undo twinkle foo",
        ),
        pytest.param(
            "foo bar" * 100,
            "baz" * 500,
            "",
            [],
            "baz" * 500,
            id="no comment",
        ),
    ],
)
def test_check_diff(
    mocker,
    mock_filename_regex,
    old_text,
    new_comment,
    new_text,
    new_tags,
    added_text,
):
    page = pywikibot.Page(SITE, "Barack Obama")
    old_rev = Revision(
        revid=1088665641,
        comment="some edit summary",
        slots={"main": {"*": old_text}},
        tags=[],
        user="A",
    )
    new_rev = Revision(
        revid=1089519971,
        comment=new_comment,
        slots={"main": {"*": new_text}},
        tags=new_tags,
        user="B",
    )
    mocker.patch(
        "copypatrol_backend.check_diff.load_revisions",
        return_value={
            old_rev.revid: old_rev,
            new_rev.revid: new_rev,
        },
    )
    result = check_diff.check_diff(page, old_rev.revid, new_rev.revid)
    assert result == added_text


@pytest.mark.parametrize(
    "linked_page_exists, linked_page_slots_main, added_text",
    [
        pytest.param(
            True,
            {"*": resource("Kommet,_ihr_Hirten-1126962296.txt").strip()},
            None,
            id="new page copied text from existing page",
        ),
        pytest.param(
            False,
            {"*": "something not copied"},
            resource("Kommet,_ihr_Hirten-1126962296-cleaned.txt").strip(),
            id="new page not copied",
        ),
        pytest.param(
            True,
            {"texthidden": ""},
            resource("Kommet,_ihr_Hirten-1126962296-cleaned.txt").strip(),
            id="linked page revision hidden",
        ),
    ],
)
def test_check_diff_new_links(
    mocker,
    mock_filename_regex,
    linked_page_exists,
    linked_page_slots_main,
    added_text,
):
    mocker.patch("pywikibot.site.APISite.loadrevisions")
    mocker.patch("pywikibot.Page.exists", return_value=linked_page_exists)
    mocker.patch(
        "pywikibot.Page.revisions",
        return_value=[
            Revision(
                revid=987654321,
                comment="something",
                slots={
                    "main": linked_page_slots_main,
                },
                tags=["foo"],
                user="C",
            ),
        ],
    )
    page = pywikibot.Page(SITE, "Kommet, ihr Hirten")
    new_rev = Revision(
        revid=1126962296,
        comment="some text copied from [[example]]",
        slots={
            "main": {
                "*": resource("Kommet,_ihr_Hirten-1126962296.txt"),
            }
        },
        tags=[],
        user="B",
    )
    mocker.patch(
        "copypatrol_backend.check_diff.load_revisions",
        return_value={
            new_rev.revid: new_rev,
        },
    )
    assert check_diff.check_diff(page, 0, new_rev.revid) == added_text


def test_check_diff_deleted(mocker):
    mocker.patch(
        "copypatrol_backend.check_diff.load_revisions",
        return_value=None,
    )
    page = pywikibot.Page(SITE, "Kommet, ihr Hirten")
    assert check_diff.check_diff(page, 1125722395, 1126962296) is None


@pytest.mark.parametrize(
    "old_slots_main, new_slots_main",
    [
        pytest.param(
            {"texthidden": ""},
            {"*": resource("Kommet,_ihr_Hirten-1126962296.txt")},
            id="old rev text hidden",
        ),
        pytest.param(
            {"*": resource("Kommet,_ihr_Hirten-1125722395.txt")},
            {"texthidden": ""},
            id="new rev text hidden",
        ),
        pytest.param(
            {"texthidden": ""},
            {"texthidden": ""},
            id="both revs text hidden",
        ),
    ],
)
def test_check_diff_rev_text_hidden(
    mocker,
    old_slots_main,
    new_slots_main,
):
    page = pywikibot.Page(SITE, "Kommet, ihr Hirten")
    old_rev = Revision(
        revid=1125722395,
        comment="some edit summary",
        slots={"main": old_slots_main},
        tags=[],
        user="A",
    )
    new_rev = Revision(
        revid=1126962296,
        comment="another edit summary",
        slots={"main": new_slots_main},
        tags=[],
        user="B",
    )
    mocker.patch(
        "copypatrol_backend.check_diff.load_revisions",
        return_value={
            old_rev.revid: old_rev,
            new_rev.revid: new_rev,
        },
    )
    result = check_diff.check_diff(page, old_rev.revid, new_rev.revid)
    assert result is None
