from __future__ import annotations

import pytest
import pywikibot

from copypatrol_backend import config


def test_meta_config():
    expected = config.MetaConfig(
        domains=["en.wikipedia.org", "es.wikipedia.org"],
        url_ignore_list_title="example-url-title",
        user_ignore_list_title="example-user-title",
    )
    assert config.meta_config.__wrapped__() == expected


def test_tca_config():
    expected = config.TCAConfig(
        domain="wikimedia.tii-sandbox.com",
        key="test-tca-key",
        webhook_domain="test-webhook-domain.com",
        webhook_signing_secret=b"test-signing-secret",
    )
    assert config.tca_config.__wrapped__() == expected


@pytest.mark.parametrize(
    "domain, expected",
    [
        (
            "en.wikipedia.org",
            config.SiteConfig(
                domain="en.wikipedia.org",
                enabled=True,
                namespaces=[0, 2, 118],
                pagetriage_namespaces=[0, 118],
            ),
        ),
        (
            "es.wikipedia.org",
            config.SiteConfig(
                domain="es.wikipedia.org",
                enabled=True,
                namespaces=[0, 2],
                pagetriage_namespaces=[],
            ),
        ),
        (
            "fr.wikipedia.org",
            config.SiteConfig(
                domain="fr.wikipedia.org",
                enabled=False,
                namespaces=[0],
                pagetriage_namespaces=[],
            ),
        ),
    ],
)
def test_site_config(domain, expected):
    assert config.site_config.__wrapped__(domain) == expected


def test_url_ignore_list(mocker):
    text = r"""
# comment
 # space before comment
 \b.*\.wikipedia\.org\b # Wikipedia
\b192\.168\.1\.1\b  # IP
 \b\zee\b # invalid
"""
    expected = [r"\b.*\.wikipedia\.org\b", r"\b192\.168\.1\.1\b"]
    mocker.patch(
        "pywikibot.Page.text",
        new_callable=mocker.PropertyMock,
        return_value=text,
    )
    result = [p.pattern for p in config.url_ignore_list.__wrapped__()]
    assert result == expected


def test_url_ignore_list_none(mocker):
    mocker.patch(
        "copypatrol_backend.config.MetaConfig.url_ignore_list_title",
        new_callable=mocker.PropertyMock,
        return_value="",
    )
    assert config.url_ignore_list() == []


def test_user_ignore_list(mocker):
    def _gen():
        site = pywikibot.Site()
        yield pywikibot.Page(site, "User:Example")
        yield pywikibot.Page(site, "User:Exemple")

    mocker.patch("pywikibot.Page.linkedPages", return_value=_gen())
    assert config.user_ignore_list.__wrapped__() == {
        "Example",
        "Exemple",
    }
