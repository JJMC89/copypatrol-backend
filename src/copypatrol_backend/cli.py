from __future__ import annotations

import argparse
import datetime
import multiprocessing.pool
import operator

import pywikibot
from pywikibot.exceptions import InvalidTitleError
from sqlalchemy.exc import IntegrityError, OperationalError

from copypatrol_backend import database, tca
from copypatrol_backend.check_diff import check_diff
from copypatrol_backend.stream_listener import change_stream


def store_changes(
    *,
    since: datetime.datetime | None = None,
    total: int | None = None,
) -> None:
    sessionmaker = database.create_sessionmaker()
    for event in change_stream(since=since, total=total):
        try:
            with sessionmaker.begin() as session:
                database.add_revision(
                    session=session,
                    page=pywikibot.Page(
                        pywikibot.Site(url=event["meta"]["uri"]),
                        event["page"]["page_title"],
                    ),
                    rev_id=event["revision"]["rev_id"],
                    rev_parent_id=event["revision"].get("rev_parent_id", 0),
                    rev_timestamp=event["revision"]["rev_dt"],
                    rev_user_text=event["revision"]["editor"]["user_text"],
                )
        except (IntegrityError, InvalidTitleError) as e:  # pragma: no cover
            pywikibot.warning(e)


def _check_diff(
    diff: database.QueuedDiff,
) -> tuple[database.QueuedDiff, str | None] | Exception:
    try:
        return diff, check_diff(diff.page, diff.rev_parent_id, diff.rev_id)
    except Exception as e:  # pragma: no cover
        pywikibot.exception()
        return e


def check_changes(*, poolsize: int = 1, limit: int | None = None) -> None:
    sessionmaker = database.create_sessionmaker()
    with sessionmaker.begin() as session:
        diffs = database.diffs_by_status(
            session,
            database.QueuedDiff,
            [database.Status.UNSUBMITTED, database.Status.CREATED],
            limit=limit,
        )
    if not diffs:
        return
    api = tca.TurnitinCoreAPI()
    chunksize, extra = divmod(len(diffs), poolsize * 4)
    if extra:
        chunksize += 1
    pywikibot.debug(f"Pool({poolsize}) {chunksize=} for {len(diffs)} diffs")
    with multiprocessing.Pool(poolsize) as pool:
        for res in pool.imap_unordered(_check_diff, diffs, chunksize):
            if isinstance(res, Exception):
                continue
            diff, text = res
            with sessionmaker() as session:
                session.add(diff)
                if text is None:
                    session.delete(diff)
                    try:
                        session.commit()
                    except OperationalError:  # pragma: no cover
                        pywikibot.exception(exc_info=False)
                    continue
                if diff.submission_id is None:
                    title = f"Revision {diff.rev_id} of {diff.page.title()}"
                    try:
                        diff.submission_id = api.create_submission(
                            site=diff.site,
                            title=title,
                            timestamp=diff.rev_timestamp,
                            owner=diff.rev_user_text,
                        )
                    except Exception:  # pragma: no cover
                        pywikibot.exception()
                        continue
                    else:
                        diff.status = database.Status.CREATED
                        session.commit()
                try:
                    api.upload_submission(diff.submission_id, text)
                except Exception:  # pragma: no cover
                    pywikibot.exception()
                else:
                    diff.status = database.Status.UPLOADED
                    session.commit()


def generate_reports(*, delta: datetime.timedelta | None = None) -> None:
    api = tca.TurnitinCoreAPI()
    with database.create_sessionmaker().begin() as session:
        for diff in database.diffs_by_status(
            session,
            database.QueuedDiff,
            database.Status.UPLOADED,
            delta=delta,
        ):
            assert diff.submission_id is not None
            try:
                info = api.submission_info(diff.submission_id)
            except Exception:  # pragma: no cover
                pywikibot.exception()
                continue
            api.handle_submission_info(info=info, diff=diff)


def check_reports(*, delta: datetime.timedelta | None = None) -> None:
    api = tca.TurnitinCoreAPI()
    with database.create_sessionmaker().begin() as session:
        for diff in database.diffs_by_status(
            session,
            database.QueuedDiff,
            database.Status.PENDING,
            delta=delta,
        ):
            assert diff.submission_id is not None
            try:
                info = api.report_info(diff.submission_id)
            except Exception:  # pragma: no cover
                pywikibot.exception()
                continue
            api.handle_similarity_info(info=info, diff=diff)


def update_ready_diffs(*, delta: datetime.timedelta | None = None) -> None:
    with database.create_sessionmaker()() as session:
        for diff in database.diffs_by_status(
            session,
            database.Diff,
            database.Status.READY,
            delta=delta,
            op=operator.ge,
        ):
            try:
                res = diff.update_page()
            except pywikibot.exceptions.Error:  # pragma: no cover
                pywikibot.exception()
            else:
                if res is None:
                    diff.status = database.Status.FIXED
                    diff.status_user_text = diff.site.username()
                session.commit()


def parse_script_args(*args: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="copypatrol backend",
        allow_abbrev=False,
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    description = "store recent changes to be checked"
    store_subparser = subparsers.add_parser(
        "store-changes",
        description=description,
        help=description,
        allow_abbrev=False,
    )
    store_subparser.add_argument(
        "--since",
        type=datetime.datetime.fromisoformat,
        help="since the timestamp",
        metavar="YYYY-MM-DD HH:MM:SS",
    )
    store_subparser.add_argument(
        "--total",
        type=int,
        help="maximum number to store",
        metavar="N",
    )
    description = "check stored changes"
    check_subparser = subparsers.add_parser(
        "check-changes",
        description=description,
        help=description,
        allow_abbrev=False,
    )
    check_subparser.add_argument(
        "--poolsize",
        default=multiprocessing.cpu_count(),
        type=int,
        help="size of the multiprocessing pool (default: %(default)s)",
        metavar="N",
    )
    check_subparser.add_argument(
        "--limit",
        type=int,
        help="maximum number to check",
        metavar="N",
    )
    description = "check and generate reports"
    subparsers.add_parser(
        "reports",
        description=description,
        help=description,
        allow_abbrev=False,
    )
    description = "update ready diffs for deletions and moves"
    subparsers.add_parser(
        "update-ready-diffs",
        description=description,
        help=description,
        allow_abbrev=False,
    )
    description = "setup database and (optionally) webhook"
    setup_subparser = subparsers.add_parser("setup", allow_abbrev=False)
    setup_subparser.add_argument(
        "--webhook",
        action="store_true",
        help="create the TCA webhook after deleting any existing",
    )
    return parser.parse_args(args=args)


def cli(*args: str) -> int:
    local_args = pywikibot.handle_args(args, do_help=False)
    parsed_args = parse_script_args(*local_args)
    if parsed_args.action == "store-changes":
        store_changes(since=parsed_args.since, total=parsed_args.total)
    elif parsed_args.action == "check-changes":
        check_changes(limit=parsed_args.limit, poolsize=parsed_args.poolsize)
    elif parsed_args.action == "reports":
        delta = datetime.timedelta(minutes=-30)
        check_reports(delta=delta)
        generate_reports(delta=delta)
    elif parsed_args.action == "update-ready-diffs":
        update_ready_diffs(delta=datetime.timedelta(weeks=-1))
    elif parsed_args.action == "setup":
        database.create_tables()
        if parsed_args.webhook:
            api = tca.TurnitinCoreAPI()
            api.delete_webhooks()
            api.create_webhook()
    return 0
