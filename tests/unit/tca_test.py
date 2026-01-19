from __future__ import annotations

from contextlib import nullcontext
from uuid import UUID

import pytest
import pywikibot
from requests.exceptions import HTTPError

from copypatrol_backend.database import Source
from copypatrol_backend.tca import TurnitinCoreAPI
from testing.resources import resource


SID = UUID("7b3074cf-4d3b-4648-8c68-f56aee0f1058")


@pytest.fixture
def mock_tca_eula(mock_responses):
    mock_responses._add_from_file(file_path="testing/unit/eula.yaml")
    yield


def test_latest_eula_version(mock_tca_eula):
    assert TurnitinCoreAPI().latest_eula_version() == "v1beta"


def test_accept_eula(mock_tca_eula):
    TurnitinCoreAPI().accept_eula("v1beta")


def test_create_submission(mock_responses):
    mock_responses._add_from_file(
        file_path="testing/unit/create-submission.yaml"
    )
    assert (
        TurnitinCoreAPI().create_submission(
            site=pywikibot.Site("en", "wikipedia"),
            title="unit test submission",
            timestamp=pywikibot.Timestamp.set_timestamp(
                "2022-12-02T02:12:22Z"
            ),
            owner="Example",
        )
        == SID
    )


@pytest.mark.parametrize(
    "case, context",
    [
        ("success", nullcontext()),
        ("eula", nullcontext()),
        ("conflict", nullcontext()),
        ("large", pytest.raises(HTTPError)),
    ],
)
def test_upload_submission(mock_responses, mock_tca_eula, case, context):
    mock_responses._add_from_file(
        file_path=f"testing/unit/upload-submission-{case}.yaml"
    )
    with context:
        TurnitinCoreAPI().upload_submission(
            SID,
            resource("Kommet,_ihr_Hirten-1126962296-added.txt"),
        )


def test_submission_info_complete(mock_responses):
    mock_responses._add_from_file(
        file_path="testing/unit/submission-info-complete.yaml"
    )
    info = TurnitinCoreAPI().submission_info(SID)
    assert info["status"] == "COMPLETE"


def test_submission_info_error(mock_responses):
    mock_responses._add_from_file(
        file_path="testing/unit/submission-info-error.yaml"
    )
    info = TurnitinCoreAPI().submission_info(SID)
    assert info["status"] == "ERROR"
    assert info["error_code"] == "PROCESSING_ERROR"


def test_generate_report(mock_responses):
    mock_responses._add_from_file(
        file_path="testing/unit/generate-report.yaml"
    )
    TurnitinCoreAPI().generate_report(SID)


def test_report_info(mock_responses):
    mock_responses._add_from_file(file_path="testing/unit/report-info.yaml")
    info = TurnitinCoreAPI().report_info(SID)
    assert info["status"] == "COMPLETE"
    assert info["top_source_largest_matched_word_count"] == 100


SOURCES = [
    Source(
        submission_id=SID,
        description="http://www.oocities.org/heartland/pines/1107/clyrics4.html",
        url="http://www.oocities.org/heartland/pines/1107/clyrics4.html",
        percent=89.28571,
    ),
]


def test_report_sources(mock_responses):
    mock_responses._add_from_file(file_path="testing/unit/report-sources.yaml")
    assert TurnitinCoreAPI().report_sources(SID) == SOURCES
