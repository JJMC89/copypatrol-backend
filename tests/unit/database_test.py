from __future__ import annotations

import uuid

import pytest
from pywikibot.page import Revision
from pywikibot.time import Timestamp
from sqlalchemy import Dialect, LargeBinary

from copypatrol_backend import database

database.BinaryDecoratorBase.impl = LargeBinary


DIALECT = Dialect()
UUID = uuid.uuid4()


@pytest.mark.parametrize(
    "value1,value2",
    [
        (None, None),
        ("Example", b"Example"),
        ("Éxàmþlë", "Éxàmþlë".encode()),
        ("ﭗﭧﭷﮇﮗ", "ﭗﭧﭷﮇﮗ".encode()),
        ("𒀇𒀗𒀧𒀷𒁇𒁗𒁧𒁷", "𒀇𒀗𒀧𒀷𒁇𒁗𒁧𒁷".encode()),
    ],
)
def test_binarydecoratorbase_process(value1, value2):
    bb = database.BinaryDecoratorBase(255)
    assert bb.process_bind_param(value1, DIALECT) == value2
    assert bb.process_result_value(value2, DIALECT) == value1


@pytest.mark.parametrize(
    "value1,value2",
    [
        (None, None),
        (UUID, str(UUID).encode()),
        ("123456789", b"123456789"),
    ],
)
def test_siddecorator_process(value1, value2):
    sid_ = database.SidDecorator(36)
    assert sid_.process_bind_param(value1, DIALECT) == value2
    assert sid_.process_result_value(value2, DIALECT) == value1


@pytest.mark.parametrize(
    "value1,value2",
    [(database.Status(i), i) for i in range(-4, 1)],
)
def test_statusdecorator_process(value1, value2):
    s = database.StatusDecorator()
    assert s.process_bind_param(value1, DIALECT) == value2
    assert s.process_result_value(value2, DIALECT) == value1


def test_timestampdecorator_process():
    ts = database.TimestampDecorator(14)
    value1 = Timestamp(2023, 1, 2, 3, 4, 5)
    value2 = b"20230102030405"
    assert ts.process_bind_param(value1, DIALECT) == value2
    assert ts.process_result_value(value2, DIALECT) == value1


@pytest.mark.parametrize(
    "ns,title,revs",
    [
        (
            2,
            "Example_user/Example_title",
            {
                456: Revision(
                    pageid=5,
                    ns=2,
                    title="User:Example user/Example title",
                ),
            },
        ),
        (
            0,
            "Example_title",
            None,
        ),
    ],
)
def test_diff_update_page(mocker, ns, title, revs):
    now = Timestamp.utcnow()
    diff = database.Diff(
        submission_id=UUID,
        project="wikipedia",
        lang="en",
        page_namespace=0,
        page_title="Example_title",
        rev_id=456,
        rev_parent_id=123,
        rev_timestamp=Timestamp(2023, 1, 2, 3, 4, 5),
        rev_user_text="Example user",
        status=database.Status.PENDING,
        status_timestamp=Timestamp(2023, 1, 2, 6, 7, 8),
        sources=[],
    )
    expected = database.Diff(
        submission_id=UUID,
        project="wikipedia",
        lang="en",
        page_namespace=ns,
        page_title=title,
        rev_id=456,
        rev_parent_id=123,
        rev_timestamp=Timestamp(2023, 1, 2, 3, 4, 5),
        rev_user_text="Example user",
        status=database.Status.PENDING,
        status_timestamp=now,
        sources=[],
    )
    mocker.patch(
        "copypatrol_backend.database.wiki.load_revisions",
        return_value=revs,
    )
    diff.update_page()
    diff.status_timestamp = now
    assert diff == expected
