from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pywikibot.comms.eventstreams import EventStreams

from copypatrol_backend import config


if TYPE_CHECKING:
    import datetime
    from collections.abc import Generator


def stream_filter(data: dict[str, Any], /) -> bool:
    if data["page_change_kind"] not in ("create", "edit"):
        return False
    if data["revision"]["rev_size"] < 500:
        return False
    old_rev = data.get("prior_state", {}).get("revision", {})
    if data["revision"]["rev_sha1"] == old_rev.get("rev_sha1"):
        return False
    domain = data["meta"]["domain"]
    if domain not in config.meta_config().domains:
        return False
    namespaces = config.site_config(domain).namespaces
    if data["page"]["namespace_id"] not in namespaces:
        return False
    if (
        data["revision"]["editor"]["is_bot"]
        or data["revision"]["editor"]["is_system"]
        or data["revision"]["editor"]["user_text"] in config.user_ignore_list()
    ):
        return False
    return True


def change_stream(
    *,
    since: datetime.datetime | None = None,
    total: int | None = None,
) -> Generator[dict[str, Any], None, None]:
    stream = EventStreams(
        streams="mediawiki.page_change.v1",
        since=since,
    )
    stream.register_filter(stream_filter)
    stream.set_maximum_items(total)
    yield from stream
