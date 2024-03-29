from __future__ import annotations

import datetime
import uuid

import pytest
import pywikibot
from pywikibot.time import Timestamp
from sqlalchemy.sql.expression import text

from copypatrol_backend import database


UUID = uuid.uuid4()


@pytest.fixture
def diffs_data(request, db_session):
    sql_dct = {
        k: v.encode() if isinstance(v, str) else v
        for k, v in request.param.items()
    }
    cols = ", ".join(sql_dct)
    vals = ", ".join(f":{key}" for key in sql_dct)
    stmt = text(f"INSERT INTO `diffs_queue` ({cols}) VALUES ({vals})")
    db_session.execute(stmt, sql_dct)
    db_session.commit()
    yield


def test_diff_from_queueddiff():
    rev_timestamp = pywikibot.Timestamp.utcnow()
    diff = database.QueuedDiff(
        project="wikipedia",
        lang="es",
        page_namespace=2,
        page_title="Examplé",
        rev_id=1000,
        rev_parent_id=1001,
        rev_timestamp=rev_timestamp,
        rev_user_text="Example",
    )
    diff.submission_id = UUID
    sources = [
        database.Source(
            submission_id=UUID,
            description="first",
            url=None,
            percent=75.38,
        ),
        database.Source(
            submission_id=UUID,
            description="second",
            url="http://example.com/",
            percent=57.83,
        ),
    ]
    result = database.Diff.from_queueddiff(diff, sources)
    expected = database.Diff(
        submission_id=UUID,
        project="wikipedia",
        lang="es",
        page_namespace=2,
        page_title="Examplé",
        rev_id=1000,
        rev_parent_id=1001,
        rev_timestamp=rev_timestamp,
        rev_user_text="Example",
        status=database.Status.READY,
        status_timestamp=result.status_timestamp,
        sources=sources,
    )
    assert result == expected


def test_diff_properties():
    diff = database.QueuedDiff(
        project="wikipedia",
        lang="es",
        page_namespace=2,
        page_title="Examplé",
        rev_id=1000,
        rev_parent_id=1001,
        rev_timestamp=pywikibot.Timestamp.utcnow(),
        rev_user_text="Example",
    )
    site = pywikibot.Site("es", "wikipedia")
    assert diff.site == site
    assert diff.page == pywikibot.Page(site, "Examplé", 2)


def test_add_revision(db_session):
    site = pywikibot.Site("en", "wikipedia")
    page = pywikibot.Page(site, "Add revision")
    database.add_revision(
        session=db_session,
        page=page,
        rev_id=1001,
        rev_parent_id=1000,
        rev_timestamp="2022-01-01T01:01:01Z",
        rev_user_text="Examplé",
    )
    db_session.commit()
    expected = {
        "project": b"wikipedia",
        "lang": b"en",
        "page_namespace": 0,
        "page_title": b"Add_revision",
        "rev_id": 1001,
        "rev_parent_id": 1000,
        "rev_timestamp": b"20220101010101",
        "rev_user_text": "Examplé".encode(),
        "submission_id": None,
        "status": database.Status.UNSUBMITTED.value,
    }
    stmt = text("SELECT * FROM `diffs_queue` WHERE `page_title` = :title")
    result = db_session.execute(stmt, {"title": b"Add_revision"}).all()
    assert len(result) == 1
    res = result[0]._asdict()
    assert res.pop("diff_queue_id") is not None
    assert res.pop("status_timestamp") is not None
    assert res == expected


@pytest.mark.parametrize(
    "diffs_data",
    [
        {
            "project": "wikipedia",
            "lang": "en",
            "page_namespace": 0,
            "page_title": "Diff_from_submission_id",
            "rev_id": 2001,
            "rev_parent_id": 2000,
            "rev_timestamp": "20220101010101",
            "rev_user_text": "Example",
            "submission_id": str(UUID),
            "status": database.Status.PENDING.value,
            "status_timestamp": "20220101020202",
        },
    ],
    indirect=True,
)
def test_queued_diff_from_submission_id(db_session, diffs_data):
    result = database.queued_diff_from_submission_id(db_session, UUID)
    assert result is not None
    assert result.submission_id == UUID


@pytest.mark.parametrize(
    "diffs_data,status",
    [
        (
            {
                "project": "wikipedia",
                "lang": "en",
                "page_namespace": 0,
                "page_title": "Records_by_status",
                "rev_id": 3000 + status,
                "rev_parent_id": 3000,
                "rev_timestamp": "20220101010101",
                "rev_user_text": "Example",
                "status": status,
                "status_timestamp": Timestamp.utcnow().totimestampformat(),
            },
            status,
        )
        for status in range(-4, 0)
    ],
    indirect=["diffs_data"],
)
def test_queued_diffs_by_status(db_session, diffs_data, status):
    result = database.queued_diffs_by_status(
        db_session, database.Status(status)
    )
    assert len(result) == 1
    assert result[0].status is database.Status(status)
    result = database.queued_diffs_by_status(
        db_session,
        [database.Status(status)],
        delta=datetime.timedelta(hours=-1),
    )
    assert len(result) == 0
