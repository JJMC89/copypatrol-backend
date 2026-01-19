from __future__ import annotations

import configparser
import functools
import os
import os.path
import re
from typing import NamedTuple

import cachetools.func
import pywikibot

CONFIGS = [os.path.expanduser("~/.copypatrol.ini"), ".copypatrol.ini"]


class MetaConfig(NamedTuple):
    domains: list[str]
    url_ignore_list_title: str
    user_ignore_list_title: str


class SiteConfig(NamedTuple):
    domain: str
    enabled: bool
    namespaces: list[int]
    pagetriage_namespaces: list[int]


class TCAConfig(NamedTuple):
    domain: str
    key: str
    webhook_domain: str | None
    webhook_signing_secret: bytes | None


def config_parser() -> configparser.ConfigParser:
    return configparser.ConfigParser(
        converters={
            "listint": lambda x: [int(i) for i in x.split(",")],
        },
        default_section="copypatrol",
        interpolation=None,
    )


@cachetools.func.ttl_cache(maxsize=1, ttl=3600)
def meta_config() -> MetaConfig:
    parser = config_parser()
    parser.read(CONFIGS)
    domains = [
        section.removeprefix("copypatrol:")
        for section in parser.sections()
        if section.startswith("copypatrol:")
        if parser.getboolean(section, "enabled", fallback=False)
    ]
    assert domains
    meta = parser["copypatrol"]
    return MetaConfig(
        domains=domains,
        url_ignore_list_title=meta.get("url-ignore-list-title", ""),
        user_ignore_list_title=meta.get("user-ignore-list-title", ""),
    )


@cachetools.func.ttl_cache(maxsize=None, ttl=3600)
def site_config(domain: str) -> SiteConfig:
    parser = config_parser()
    parser.read(CONFIGS)
    section = parser[f"copypatrol:{domain}"]
    if os.environ.get("CPB_ENV") in ("prod", "pytest-unit"):
        pt_ns = section.getlistint("pagetriage-namespaces", [])
    else:  # pragma: no cover
        pt_ns = []
    return SiteConfig(
        domain=domain,
        enabled=section.getboolean("enabled", False),
        namespaces=section.getlistint("namespaces", [0]),
        pagetriage_namespaces=pt_ns,
    )


@functools.cache
def tca_config() -> TCAConfig:
    return TCAConfig(
        domain=os.environ["CPB_TCA_DOMAIN"],
        key=os.environ["CPB_TCA_KEY"],
        webhook_domain=os.environ.get("CPB_TCA_WEBHOOK_DOMAIN"),
        webhook_signing_secret=(
            secret.encode("ascii")
            if (secret := os.environ.get("CPB_TCA_WEBHOOK_SIGNING_SECRET"))
            else None
        ),
    )


@cachetools.func.ttl_cache(maxsize=1, ttl=3600)
def url_ignore_list() -> list[re.Pattern[str]]:
    result: list[re.Pattern[str]] = []
    if not meta_config().url_ignore_list_title:
        return result
    page = pywikibot.Page(
        pywikibot.Site(),
        meta_config().url_ignore_list_title,
    )
    for line in page.text.splitlines():
        line, _, _ = line.partition("#")
        line = line.strip()
        if not line:
            continue
        try:
            result.append(re.compile(line, flags=re.I))
        except Exception:
            pywikibot.exception(exc_info=False)
            pywikibot.error(f"invalid regex ignored: {line!r}")
    return result


@cachetools.func.ttl_cache(maxsize=1, ttl=3600)
def user_ignore_list() -> set[str]:
    site = pywikibot.Site()
    page = pywikibot.page.Page(site, meta_config().user_ignore_list_title)
    links = page.linkedPages(namespaces=site.namespaces.USER)
    return {pywikibot.page.User(page).username for page in links}
