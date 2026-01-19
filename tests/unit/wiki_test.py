from __future__ import annotations

import pywikibot

from copypatrol_backend import wiki
from testing.resources import resource

SITE = pywikibot.Site("en", "wikipedia")


def test_load_revisions(mock_responses):
    revids = [1125722395, 1126962296]
    if SITE.is_oauth_token_available():  # pragma: no cover
        path = "testing/unit/load-revisions-oauth.yaml"
    else:  # pragma: no cover
        path = "testing/unit/load-revisions-nooauth.yaml"
    mock_responses._add_from_file(file_path=path)
    res = wiki.load_revisions(SITE, revids, content=True)
    assert res is not None
    for revid in revids:
        assert revid in res
        assert res[revid].revid == revid
        expected_text = resource(f"Kommet,_ihr_Hirten-{revid}.txt").strip()
        assert res[revid].text == expected_text
        assert res[revid].commenthidden is False
    assert res[1125722395].comment == "See also 'List of Christmas carols"
    assert res[1125722395].tags == []
    assert (
        res[1126962296].comment
        == "better LilyPond score, incl. repeat; +English text."
    )
    assert res[1126962296].tags == ["wikieditor"]


def test_load_revisions_badrevids(mocker):
    mocker.patch.object(
        pywikibot.data.api.Request,
        "submit",
        return_value={
            "query": {
                "badrevids": {
                    "1167163687": {"revid": 1167163687, "missing": ""}
                }
            }
        },
    )
    assert wiki.load_revisions(SITE, [1167163687]) is None
