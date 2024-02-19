from __future__ import annotations

import datetime
import multiprocessing
from argparse import Namespace

import pytest

from copypatrol_backend import cli


@pytest.mark.parametrize(
    "args, expected",
    [
        pytest.param(
            ("store-changes",),
            Namespace(action="store-changes", since=None, total=None),
            id="store-changes",
        ),
        pytest.param(
            ("store-changes", "--since", "2022-01-01T00:00:00"),
            Namespace(
                action="store-changes",
                since=datetime.datetime(2022, 1, 1, 0, 0, 0),
                total=None,
            ),
            id="store-changes since",
        ),
        pytest.param(
            ("store-changes", "--total", "10"),
            Namespace(
                action="store-changes",
                since=None,
                total=10,
            ),
            id="store-changes total",
        ),
        pytest.param(
            ("check-changes",),
            Namespace(
                action="check-changes",
                poolsize=multiprocessing.cpu_count(),
                limit=None,
            ),
            id="check-changes",
        ),
        pytest.param(
            (
                "check-changes",
                "--poolsize",
                "3",
            ),
            Namespace(action="check-changes", poolsize=3, limit=None),
            id="check-changes poolsize",
        ),
        pytest.param(
            (
                "check-changes",
                "--poolsize",
                "3",
                "--limit",
                "10",
            ),
            Namespace(action="check-changes", poolsize=3, limit=10),
            id="check-changes limit",
        ),
        pytest.param(
            ("reports",),
            Namespace(action="reports"),
            id="reports",
        ),
        pytest.param(
            ("setup",),
            Namespace(
                action="setup",
                webhook=False,
            ),
            id="setup without webhook",
        ),
        pytest.param(
            ("setup", "--webhook"),
            Namespace(
                action="setup",
                webhook=True,
            ),
            id="setup with webhook",
        ),
    ],
)
def test_parse_script_args(args, expected):
    assert cli.parse_script_args(*args) == expected


@pytest.mark.parametrize(
    "args",
    [
        ("foo",),
        ("store-changes", "--foo", "bar"),
        ("store-changes", "--since", "2022-01-01T00:00:00", "--total", "ten"),
        ("store-changes", "--since", "2022-01-01T00:00:00", "--foo"),
        ("check-changes", "foo"),
        ("check-changes", "--limit", "ten"),
        ("check-changes", "--workers", "3"),
        ("reports", "foo"),
        ("setup", "--foo"),
    ],
)
def test_parse_script_args_exits(args):
    with pytest.raises(SystemExit):
        cli.parse_script_args(*args)
