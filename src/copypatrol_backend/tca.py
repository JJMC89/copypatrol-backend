from __future__ import annotations

import base64
import importlib.metadata
from typing import TYPE_CHECKING, Any, Union
from uuid import UUID

import pywikibot
import requests
from pywikibot.time import Timestamp
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError, JSONDecodeError
from requests.utils import default_user_agent
from sqlalchemy.orm import object_session
from urllib3.util import Retry

from copypatrol_backend import config, database, wiki

if TYPE_CHECKING:
    from pywikibot.site import APISite


_VERSION = importlib.metadata.version("copypatrol_backend")
WEBHOOK_EVENT_TYPES = ["SUBMISSION_COMPLETE", "SIMILARITY_COMPLETE"]

_JSON = Union[bool, float, str, None, dict[str, "_JSON"], list["_JSON"]]
JSON = dict[str, _JSON]


class TurnitinCoreAPI:
    def __init__(self) -> None:
        super().__init__()
        self.config = config.tca_config()
        self.base_url = f"https://{self.config.domain}/api/v1"
        retry = Retry(
            total=pywikibot.config.max_retries,
            status_forcelist=(429, 500),
            backoff_factor=1,
            backoff_max=pywikibot.config.retry_max,
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.config.key}",
                "User-Agent": (
                    f"copypatrol-backend-bot/{_VERSION} "
                    f"({default_user_agent()})"
                ),
                "X-Turnitin-Integration-Name": "CopyPatrol backend",
                "X-Turnitin-Integration-Version": _VERSION,
            }
        )
        self.session.mount(self.base_url, HTTPAdapter(max_retries=retry))

    def read_response(self, response: requests.Response, /) -> dict[str, Any]:
        if response.status_code == 451:
            # accept latest eula and retry
            self.accept_eula(self.latest_eula_version())
            return self.read_response(self.session.send(response.request))
        try:
            response.raise_for_status()
            return response.json() if response.text else {}
        except (HTTPError, JSONDecodeError) as e:
            pywikibot.log(e)
            pywikibot.log(f"response: {response.text}")
            raise

    def latest_eula_version(self) -> str:
        response = self.session.get(
            f"{self.base_url}/eula/latest",
            params={"lang": "en-US"},
        )
        data = self.read_response(response)
        ret = data["version"]
        assert isinstance(ret, str)
        return ret

    def accept_eula(self, version: str, /) -> None:
        pywikibot.info(f"accepting EULA {version=}")
        response = self.session.post(
            f"{self.base_url}/eula/{version}/accept",
            json={
                "version": version,
                "user_id": ":system:",
                "accepted_timestamp": Timestamp.utcnow().isoformat(),
                "language": "en-US",
            },
        )
        self.read_response(response)

    def create_webhook(self) -> None:
        pywikibot.info("creating webhook ...")
        assert self.config.webhook_signing_secret is not None
        base64_secret = base64.b64encode(self.config.webhook_signing_secret)
        response = self.session.post(
            f"{self.base_url}/webhooks",
            json={
                "description": "CopyPatrol backend webhook",
                "signing_secret": base64_secret.decode(),
                "url": f"https://{self.config.webhook_domain}/tca-webhook",
                "event_types": WEBHOOK_EVENT_TYPES,
            },
        )
        data = self.read_response(response)
        pywikibot.info(data)

    def delete_webhooks(self) -> None:
        r = self.session.get(f"{self.base_url}/webhooks")
        r.raise_for_status()
        for webhook in r.json():
            if webhook["description"] != "CopyPatrol backend webhook":
                continue
            id = webhook["id"]
            pywikibot.info(f"deleting webhook {id=} ...")
            response = self.session.delete(f"{self.base_url}/webhooks/{id}")
            self.read_response(response)

    def create_submission(
        self,
        *,
        site: APISite,
        title: str,
        timestamp: Timestamp,
        owner: str,
    ) -> UUID:
        pywikibot.debug(f"creating submission for {title=} ...")
        response = self.session.post(
            f"{self.base_url}/submissions",
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
        )
        data = self.read_response(response)
        sid = UUID(data["id"])
        pywikibot.debug(f"{sid=}")
        return sid

    def upload_submission(self, sid: UUID, text: str, /) -> None:
        pywikibot.debug(f"uploading submission for {sid=} ...")
        response = self.session.put(
            f"{self.base_url}/submissions/{sid}/original",
            headers={
                "Content-Type": "binary/octet-stream",
                "Content-Disposition": f"inline; filename='{sid}.txt'",
            },
            data=text.encode(),
        )
        if (
            response.status_code == 409
            and response.json().get("code") == "CONFLICT"
        ):
            pywikibot.debug(f"previous upload for {sid=}")
            return
        self.read_response(response)
        pywikibot.debug(f"upload successful for {sid=}")

    def submission_info(self, sid: UUID, /) -> JSON:
        pywikibot.debug(f"getting submission info for {sid=}")
        response = self.session.get(f"{self.base_url}/submissions/{sid}")
        data = self.read_response(response)
        assert UUID(data["id"]) == sid
        return data

    def generate_report(self, sid: UUID, /, *, priority: str = "LOW") -> None:
        pywikibot.debug(f"generating report for {sid=}")
        response = self.session.put(
            f"{self.base_url}/submissions/{sid}/similarity",
            json={
                "generation_settings": {
                    "search_repositories": [
                        "INTERNET",
                        "SUBMITTED_WORK",
                        "PUBLICATION",
                        "CROSSREF",
                        "CROSSREF_POSTED_CONTENT",
                    ],
                    "priority": priority,
                },
            },
        )
        self.read_response(response)

    def report_info(self, sid: UUID, /) -> JSON:
        pywikibot.debug(f"getting report info for {sid=}")
        response = self.session.get(
            f"{self.base_url}/submissions/{sid}/similarity"
        )
        data = self.read_response(response)
        assert UUID(data["submission_id"]) == sid
        return data

    def report_sources(self, sid: UUID, /) -> list[database.Source]:
        pywikibot.debug(f"getting sources for {sid=}")
        response = self.session.get(
            f"{self.base_url}/submissions/{sid}/similarity/view/overview",
        )
        data = self.read_response(response)
        assert UUID(data["submission_id"]) == sid
        return [
            database.Source(
                submission_id=sid,
                description=aggregate["match_sources"][0]["description"],
                url=aggregate["match_sources"][0].get("link") or None,
                percent=aggregate["match_sources"][0]["percent"],
            )
            for aggregate in data["match_aggregates"]
        ]

    def handle_submission_info(
        self,
        *,
        info: JSON,
        diff: database.QueuedDiff,
    ) -> None:
        if info["status"] == "COMPLETE":
            assert diff.submission_id is not None
            try:
                self.generate_report(diff.submission_id)
            except Exception:  # pragma: no cover
                pywikibot.exception()
            else:
                diff.status = database.Status.PENDING
        elif info["status"] == "ERROR":
            pywikibot.log(info)
            error_code = info["error_code"]
            pywikibot.error(f"submission {error_code=}")
            if error_code == "PROCESSING_ERROR":
                # retry as a new submission
                diff.submission_id = None
                diff.status = database.Status.UNSUBMITTED
            else:
                session = object_session(diff)
                assert session is not None
                session.delete(diff)
        elif info["status"] != "PROCESSING":
            pywikibot.log(info)
            pywikibot.error(f"unhandled status={info['status']}")

    def handle_similarity_info(
        self,
        *,
        info: JSON,
        diff: database.QueuedDiff,
    ) -> None:
        if info["status"] != "COMPLETE":
            return
        session = object_session(diff)
        assert session is not None
        if info["top_source_largest_matched_word_count"] == 0:
            session.delete(diff)
            return
        assert diff.submission_id is not None
        try:
            sources = self.report_sources(diff.submission_id)
        except Exception:  # pragma: no cover
            pywikibot.exception()
            return
        sources = [
            source
            for source in sources
            if source.percent > 50
            if source.url is None
            or not any(i.search(source.url) for i in config.url_ignore_list())
        ]
        if sources and (page_id := diff.update_page()):
            ready_diff = database.Diff.from_queueddiff(diff, sources)
            session.add(ready_diff)
            site_config = config.site_config(diff.site.hostname())
            if ready_diff.page_namespace in site_config.pagetriage_namespaces:
                wiki.submit_pagetriage(diff.site, page_id, diff.rev_id)
        session.delete(diff)
