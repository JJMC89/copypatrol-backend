from __future__ import annotations

import json

import pytest
import pywikibot

from copypatrol_backend import stream_listener


DATA1 = {
    "meta": {
        "domain": "en.wikipedia.org",
        "uri": "https://en.wikipedia.org/wiki/Wikipedia",
    },
    "page_namespace": 0,
    "page_title": "Wikipedia",
    "performer": {
        "user_is_bot": False,
    },
    "rev_content_changed": True,
    "rev_len": 1000,
    "rev_parent_id": 0,
    "rev_id": 1,
}
DATA2 = {
    "meta": {
        "domain": "es.wikipedia.org",
        "uri": "https://es.wikipedia.org/wiki/Ayuda:Espacio de nombres",
    },
    "page_namespace": 12,
    "page_title": "Ayuda:Espacio de nombres",
    "performer": {
        "user_is_bot": True,
    },
    "rev_content_changed": True,
    "rev_len": 500,
    "rev_parent_id": 0,
    "rev_id": 1,
}
DATA3 = {
    "meta": {
        "domain": "fr.wikipedia.org",
        "uri": "https://fr.wikipedia.org/wiki/Wikipédia",
    },
    "page_namespace": 0,
    "page_title": "Wikipédia",
    "performer": {
        "user_is_bot": False,
    },
    "rev_content_changed": True,
    "rev_len": 1000,
    "rev_parent_id": 0,
    "rev_id": 1,
}


@pytest.mark.parametrize(
    "data, expected",
    [
        (DATA1, True),
        (DATA2, False),
        (DATA3, False),
    ],
)
def test_site_filter(data, expected):
    assert stream_listener._site_filter(data) == expected


class _Event:
    def __init__(self, data):
        self.event = "message"
        self.data = json.dumps(data)


def _source(**kwargs):
    return iter([_Event(DATA1), _Event(DATA2), _Event(DATA3)])


def _code_fam_from_url(url, name):
    code = url[8:10]
    return code, "wikipedia"


def test_code_fam_from_url():
    url = "https://en.wikipedia.org/wiki/Kommet,_ihr_Hirten"
    assert _code_fam_from_url(url, "foo") == ("en", "wikipedia")


def test_revision_stream(mocker):
    mocker.patch(
        "pywikibot._code_fam_from_url",
        wraps=_code_fam_from_url,
    )
    mocker.patch("pywikibot.config.family", "wikipedia")
    mocker.patch("pywikibot.config.mylang", "en")
    site = pywikibot.Site()
    mocker.patch(
        "pywikibot.comms.eventstreams.EventSource",
        _source,
    )
    revisions = list(stream_listener.revision_stream(site, total=1))
    assert revisions == [DATA1]
