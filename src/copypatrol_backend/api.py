from __future__ import annotations

import functools
import hashlib
import hmac
from collections.abc import Callable
from typing import TYPE_CHECKING, ParamSpec, TypeVar, cast
from uuid import UUID

import flask

from copypatrol_backend import database, tca
from copypatrol_backend.config import tca_config

if TYPE_CHECKING:
    from flask.typing import ResponseReturnValue


P = ParamSpec("P")
R = TypeVar("R")


def requires_tca_webhook_headers(func: Callable[P, R]) -> Callable[P, R]:
    config = tca_config()

    @functools.wraps(func)
    def check_headers(*args: P.args, **kwargs: P.kwargs) -> R:
        event_type = flask.request.headers.get("X-Turnitin-EventType")
        if event_type not in tca.WEBHOOK_EVENT_TYPES:
            flask.abort(403)
        assert config.webhook_signing_secret is not None
        body_signature = hmac.new(
            config.webhook_signing_secret,
            flask.request.data,
            hashlib.sha256,
        ).hexdigest()
        if body_signature != flask.request.headers.get("X-Turnitin-Signature"):
            flask.abort(403)
        return func(*args, **kwargs)

    return check_headers


def application_factory() -> flask.Flask:
    api = tca.TurnitinCoreAPI()
    app = flask.Flask(__name__.split(".")[0])

    @app.route("/")
    def empty() -> ResponseReturnValue:
        return {}

    @app.route("/healthz")
    def healthz() -> ResponseReturnValue:
        with database.create_sessionmaker().begin() as session:
            queue_length = database.diff_count(
                session,
                database.QueuedDiff,
            )
            if queue_length > 0:
                queue: tca.JSON = {
                    "length": queue_length,
                    "newest": database.max_diff_timestamp(
                        session,
                        database.QueuedDiff,
                    ).isoformat(),
                    "oldest": database.min_diff_timestamp(
                        session,
                        database.QueuedDiff,
                    ).isoformat(),
                }
            else:
                queue = {
                    "length": queue_length,
                    "newest": None,
                    "oldest": None,
                }
            ready_length = database.diff_count(
                session,
                database.Diff,
                status=database.Status.READY,
            )
            if ready_length > 0:
                ready: tca.JSON = {
                    "length": ready_length,
                    "newest": database.max_diff_timestamp(
                        session,
                        database.Diff,
                        status=database.Status.READY,
                    ).isoformat(),
                    "oldest": database.min_diff_timestamp(
                        session,
                        database.Diff,
                        status=database.Status.READY,
                    ).isoformat(),
                }
            else:
                ready = {
                    "length": ready_length,
                    "newest": None,
                    "oldest": None,
                }
        return {
            "queue": queue,
            "ready": ready,
            "status": "up",
        }

    @app.route("/tca-webhook", methods=["POST"])
    @requires_tca_webhook_headers
    def tca_webhook() -> ResponseReturnValue:
        @flask.after_this_request
        def response_processor(response: flask.Response) -> flask.Response:
            @response.call_on_close
            @flask.copy_current_request_context
            def process_after_request() -> None:
                event_type = flask.request.headers["X-Turnitin-EventType"]
                info = cast(tca.JSON, flask.request.json)
                submission_id_s = info.get("submission_id") or info["id"]
                assert isinstance(submission_id_s, str)
                with database.create_sessionmaker().begin() as session:
                    diff = database.queued_diff_from_submission_id(
                        session,
                        UUID(submission_id_s),
                    )
                    if diff is None:
                        return
                    if event_type == "SUBMISSION_COMPLETE":
                        if diff.status > database.Status.UPLOADED:
                            return
                        api.handle_submission_info(info=info, diff=diff)
                    elif event_type == "SIMILARITY_COMPLETE":
                        if diff.status > database.Status.PENDING:
                            return
                        api.handle_similarity_info(info=info, diff=diff)

            return response

        return {"msg": "accepted"}

    return app
