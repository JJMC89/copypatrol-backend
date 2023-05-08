"""Turnitin Core API."""
from __future__ import annotations

from typing import TYPE_CHECKING, Union
from uuid import UUID

import pywikibot
import requests
from pywikibot.time import Timestamp
from requests.adapters import HTTPAdapter
from requests.utils import default_user_agent
from urllib3.util import Retry

from copypatrol_backend.config import tca_config
from copypatrol_backend.database import Source


if TYPE_CHECKING:
    from pywikibot.site import APISite


CONFIG = tca_config()
_VERSION = "0.0.0"
HEADERS = {
    "Authorization": f"Bearer {CONFIG.key}",
    "From": "copypatrol.backend@toolforge.org",
    "User-Agent": (
        f"copypatrol-backend-bot/{_VERSION} ({default_user_agent()})"
    ),
    "X-Turnitin-Integration-Name": "CopyPatrol",
    "X-Turnitin-Integration-Version": _VERSION,
}

_JSON = Union[bool, float, str, None, dict[str, "_JSON"], list["_JSON"]]
JSON = dict[str, _JSON]


class TurnitinCoreAPI:
    """Turnitin Core API."""

    def __init__(self) -> None:
        super().__init__()
        self._base_url = f"https://{CONFIG.domain}/api/v1"
        retry = Retry(
            total=pywikibot.config.max_retries,
            status_forcelist=(429, 500),
            backoff_factor=1,
            backoff_max=pywikibot.config.retry_max,  # type: ignore[call-arg]
        )
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._session.mount(self._base_url, HTTPAdapter(max_retries=retry))
        self._accept_eula(self._latest_eula_version())

    def _latest_eula_version(self) -> str:
        data = self._session.get(
            f"{self._base_url}/eula/latest",
            params={"lang": "en-US"},
        ).json()
        return data["version"]

    def _accept_eula(self, version: str, /) -> None:
        self._session.post(
            f"{self._base_url}/eula/{version}/accept",
            json={
                "version": version,
                "user_id": ":system:",
                "accepted_timestamp": Timestamp.utcnow().isoformat(),
                "language": "en-US",
            },
        )

    def create_submission(
        self,
        *,
        site: APISite,
        title: str,
        timestamp: Timestamp,
        owner: str,
    ) -> UUID:
        """Create a submission."""
        pywikibot.log(f"creating submission for {title=} ...")
        data = self._session.post(
            f"{self._base_url}/submissions",
            json={
                "owner": owner,
                "title": title,
                "submitter": ":system:",
                "metadata": {
                    "group": {
                        "id": str(site),
                        "name": str(site),
                        "type": "FOLDER",
                    },
                    "original_submitted_time": timestamp.isoformat(),
                },
                "owner_default_permission_set": "USER",
                "submitter_default_permission_set": "ADMINISTRATOR",
            },
        ).json()
        pywikibot.log(f"sid={data['id']}")
        return UUID(data["id"])

    def upload_submission(self, sid: UUID, text: str, /) -> None:
        """Upload text to a submission."""
        pywikibot.log(f"uploading submission for {sid=} ...")
        self._session.put(
            f"{self._base_url}/submissions/{sid}/original",
            headers={
                "Content-Type": "binary/octet-stream",
                "Content-Disposition": f"inline; filename='{sid}.txt'",
            },
            data=text.encode(),
        )
        pywikibot.log(f"upload successful for {sid=}")

    def submission_info(self, sid: UUID, /) -> JSON:
        """Get submission info."""
        pywikibot.log(f"getting submission info for {sid=}")
        data = self._session.get(f"{self._base_url}/submissions/{sid}").json()
        assert UUID(data["id"]) == sid
        return data

    def generate_report(self, sid: UUID, /, *, prioity: str = "LOW") -> None:
        """Generate a similarity report for a submission."""
        pywikibot.log(f"generating report for {sid=}")
        self._session.put(
            f"{self._base_url}/submissions/{sid}/similarity",
            json={
                "generation_settings": {
                    "search_repositories": [
                        "INTERNET",
                        "SUBMITTED_WORK",
                        "PUBLICATION",
                        "CROSSREF",
                        "CROSSREF_POSTED_CONTENT",
                    ],
                    "priority": prioity,
                },
            },
        )

    def _report_info(self, sid: UUID, /) -> JSON:
        pywikibot.log(f"getting report info for {sid=}")
        data = self._session.get(
            f"{self._base_url}/submissions/{sid}/similarity"
        ).json()
        assert UUID(data["submission_id"]) == sid
        return data

    def _report_sources(self, sid: UUID, /) -> list[Source]:
        pywikibot.log(f"getting sources for {sid=}")
        data = self._session.get(
            f"{self._base_url}/submissions/{sid}/similarity/view/sources",
        ).json()
        assert UUID(data["submission_id"]) == sid
        return [
            Source(
                submission_id=sid,
                description=source["description"],
                url=source.get("link"),
                percent=source["percent"],
            )
            for aggregate in data["match_aggregates"]
            if aggregate["is_excluded"] is False
            for source in aggregate["match_sources"]
            if source["is_excluded"] is False
        ]

    def report_sources(self, sid: UUID, /) -> list[Source] | None:
        """Return the sources found in the report."""
        info = self._report_info(sid)
        if info["status"] != "COMPLETE":
            return None
        if info["top_source_largest_matched_word_count"] == 0:
            return []
        return self._report_sources(sid)
