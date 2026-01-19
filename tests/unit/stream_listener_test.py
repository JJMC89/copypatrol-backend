from __future__ import annotations

import json

import pytest

from copypatrol_backend import stream_listener


DATA1 = {
    "meta": {
        "domain": "en.wikipedia.org",
        "uri": "https://en.wikipedia.org/wiki/Wikipedia",
    },
    "page_change_kind": "edit",
    "page": {
        "namespace_id": 0,
        "page_title": "Wikipedia",
    },
    "revision": {
        "editor": {
            "is_bot": False,
            "is_system": False,
            "user_text": "Example",
        },
        "rev_id": 123,
        "rev_parent_id": 456,
        "rev_sha1": "2fd4e1c67a2d28fced849ee1bb76e7391b93eb12",
        "rev_size": 1000,
    },
    "prior_state": {
        "revision": {
            "rev_id": 456,
            "rev_sha1": "de9f2c7fd25e1b3afad3e85a0bd17d9b100db4b3",
        },
    },
}
DATA2 = {
    "meta": {
        "domain": "es.wikipedia.org",
        "uri": "https://es.wikipedia.org/wiki/Ayuda:Espacio de nombres",
    },
    "page_change_kind": "create",
    "page": {
        "namespace_id": 0,
        "page_title": "Ejemplo",
    },
    "revision": {
        "editor": {
            "is_bot": True,
            "is_system": False,
            "user_text": "Ejemplo",
        },
        "rev_id": 789,
        "rev_sha1": "2fd4e1c67a2d28fced849ee1bb76e7391b93eb12",
        "rev_size": 500,
    },
}
DATA3 = {
    "meta": {
        "domain": "fr.wikipedia.org",
        "uri": "https://fr.wikipedia.org/wiki/Wikipédia",
    },
    "page_change_kind": "create",
    "page": {
        "namespace_id": 0,
        "page_title": "Wikipédia",
    },
    "revision": {
        "editor": {
            "is_bot": False,
            "is_system": False,
            "user_text": "Exemple",
        },
        "rev_id": 123,
        "rev_sha1": "2fd4e1c67a2d28fced849ee1bb76e7391b93eb12",
        "rev_size": 1000,
    },
}
DATA4 = DATA1 | {
    "revision": {
        "editor": {
            "is_bot": False,
            "is_system": False,
            "user_text": "Example",
        },
        "rev_id": 123,
        "rev_parent_id": 456,
        "rev_sha1": "2fd4e1c67a2d28fced849ee1bb76e7391b93eb12",
        "rev_size": 400,
    }
}
DATA5 = DATA1 | {
    "prior_state": {
        "revision": {
            "rev_sha1": "2fd4e1c67a2d28fced849ee1bb76e7391b93eb12",
        }
    }
}
DATA6 = DATA1 | {
    "page": {
        "namespace_id": 12,
        "page_title": "Help:About help pages",
    },
}


@pytest.mark.parametrize(
    "data, expected",
    [
        (DATA1, True),
        (DATA2, False),
        (DATA3, False),
        (DATA4, False),
        (DATA5, False),
        (DATA6, False),
        (DATA1 | {"page_change_kind": "move"}, False),
    ],
)
def test_stream_filter(mocker, data, expected):
    mocker.patch(
        "copypatrol_backend.stream_listener.config.user_ignore_list",
        return_value=[],
    )
    assert stream_listener.stream_filter(data) is expected


class _Event:
    def __init__(self, data):
        self.type = "message"
        self.data = json.dumps(data)


class _ES:
    def __init__(self, *args, **kwargs):
        self._i = 0
        self._data = [_Event(DATA1), _Event(DATA2), _Event(DATA3)]

    def __iter__(self):
        return self

    def __next__(self):
        if self._i < len(self._data):
            item = self._data[self._i]
            self._i += 1
            return item
        raise StopIteration

    def connect(self, *args, **kwargs):
        pass

    def close(self, *args, **kwargs):
        pass


def _code_fam_from_url(url, name):
    code = url[8:10]
    return code, "wikipedia"


def test_code_fam_from_url():
    url = "https://en.wikipedia.org/wiki/Kommet,_ihr_Hirten"
    assert _code_fam_from_url(url, "foo") == ("en", "wikipedia")


def test_change_stream(mocker):
    mocker.patch(
        "pywikibot._code_fam_from_url",
        wraps=_code_fam_from_url,
    )
    mocker.patch(
        "pywikibot.comms.eventstreams.EventSource",
        _ES,
    )
    mocker.patch(
        "copypatrol_backend.stream_listener.config.user_ignore_list",
        return_value=[],
    )
    revisions = list(stream_listener.change_stream(total=1))
    assert revisions == [DATA1]
