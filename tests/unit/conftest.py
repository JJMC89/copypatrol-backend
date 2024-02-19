from __future__ import annotations

from unittest import mock

import pytest
from pytest_socket import disable_socket  # type: ignore[import-not-found]
from responses import RequestsMock  # type: ignore[import-not-found]


def pytest_runtest_setup():
    disable_socket()


@pytest.fixture(autouse=True)
def configure_env(monkeypatch):
    monkeypatch.setenv("CPB_ENV", "pytest-unit")
    monkeypatch.setenv("CPB_DB_DRIVERNAME", "mysql+pymysql")
    monkeypatch.setenv("CPB_DB_USERNAME", "root")
    monkeypatch.setenv("CPB_DB_PASSWORD", "root")
    monkeypatch.setenv("CPB_DB_DATABASE", "copypatrol_tests")
    monkeypatch.setenv("CPB_DB_HOST", "localhost")
    monkeypatch.setenv("CPB_DB_PORT", "3306")
    monkeypatch.setenv("CPB_DB_DEFAULT_CHARACTER_SET", "utf8mb4")
    monkeypatch.setenv("CPB_TCA_DOMAIN", "wikimedia.tii-sandbox.com")
    monkeypatch.setenv("CPB_TCA_KEY", "test-tca-key")
    monkeypatch.setenv("CPB_TCA_WEBHOOK_DOMAIN", "test-webhook-domain.com")
    monkeypatch.setenv("CPB_TCA_WEBHOOK_SIGNING_SECRET", "test-signing-secret")
    yield


@pytest.fixture(autouse=True)
def configure_pywikibot(monkeypatch):
    import pywikibot.config

    monkeypatch.setattr(pywikibot.config, "family", "meta")
    monkeypatch.setattr(pywikibot.config, "mylang", "meta")
    monkeypatch.setattr(pywikibot.config, "max_retries", 0)

    yield


@pytest.fixture(autouse=True, scope="session")
def disable_pywikibot_cache():
    from pywikibot.data.api import CachedRequest, Request

    class NoCacheRequest(CachedRequest):  # type: ignore[misc] # pragma: no cover  # noqa: E501
        def submit(self):
            return Request.submit(self)

    with mock.patch("pywikibot.data.api.CachedRequest", NoCacheRequest):
        yield


@pytest.fixture(autouse=True, scope="session")
def disable_pywikibot_login():
    with mock.patch("pywikibot.site.APISite.login", return_value=True):
        yield


@pytest.fixture(autouse=True)
def mock_configs(mocker):
    mocker.patch(
        "copypatrol_backend.config.CONFIGS",
        ["testing/unit/config.ini"],
    )
    yield


@pytest.fixture(autouse=True, scope="session")
def mock_pywikibot_namespaces():
    from pywikibot.site import Namespace, NamespacesDict

    with mock.patch(
        "pywikibot.site.APISite.namespaces",
        new_callable=mock.PropertyMock,
        return_value=NamespacesDict(Namespace.builtin_namespaces()),
    ):
        yield


@pytest.fixture
def mock_responses():
    with RequestsMock(assert_all_requests_are_fired=False) as requests_mock:
        yield requests_mock
