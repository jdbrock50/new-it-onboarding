"""Isolated tests for read-only group approval CSV exports."""

import csv
from pathlib import Path

import pytest

from src import audit
from src.group_approval import GroupReviewStatus
from src.group_approval_reporting import (
    GroupApprovalReport,
    GroupReviewSummary,
    export_group_approval_report_csv,
)


@pytest.fixture(autouse=True)
def isolate_audit_storage(tmp_path, monkeypatch):
    """Keep tests away from real onboarding audit records."""
    monkeypatch.setattr(audit, "DATA_DIR", tmp_path)
    monkeypatch.setattr(audit, "AUDIT_FILE", tmp_path / "onboarding_audit.jsonl")


def sample_report(*, employee_email="alex@example.org"):
    return GroupApprovalReport(
        reviews=(
            GroupReviewSummary(
                onboarding_id="TEST-001",
                employee_email=employee_email,
                status=GroupReviewStatus.IN_PROGRESS,
                total_groups=4,
                approved=1,
                rejected=1,
                deferred=1,
                not_reviewed=1,
                reopen_count=2,
            ),
        )
    )


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_export_writes_expected_columns_and_values(tmp_path):
    destination = tmp_path / "approval-report.csv"
    export_group_approval_report_csv(sample_report(), destination)

    rows = read_rows(destination)
    assert len(rows) == 1
    assert list(rows[0]) == [
        "onboarding_id", "employee_email", "status", "total_groups",
        "approved", "rejected", "deferred", "not_reviewed", "unresolved",
        "reopen_count", "was_reopened",
    ]
    assert rows[0] == {
        "onboarding_id": "TEST-001",
        "employee_email": "alex@example.org",
        "status": "in_progress",
        "total_groups": "4",
        "approved": "1",
        "rejected": "1",
        "deferred": "1",
        "not_reviewed": "1",
        "unresolved": "2",
        "reopen_count": "2",
        "was_reopened": "True",
    }


def test_empty_report_writes_header_only(tmp_path):
    destination = tmp_path / "empty.csv"
    export_group_approval_report_csv(GroupApprovalReport(reviews=()), destination)
    assert read_rows(destination) == []
    with destination.open(encoding="utf-8-sig", newline="") as handle:
        assert len(list(csv.reader(handle))) == 1


@pytest.mark.parametrize("unsafe", ["=1+1", "+SUM(1,2)", "-1+2", "@SUM(1,2)", "\t=1+1", "\r=1+1", "\n=1+1"])
def test_export_escapes_spreadsheet_formula_prefixes(tmp_path, unsafe):
    destination = tmp_path / "safe.csv"
    export_group_approval_report_csv(sample_report(employee_email=unsafe), destination)
    assert read_rows(destination)[0]["employee_email"] == "'" + unsafe


def test_export_does_not_overwrite_existing_file(tmp_path):
    destination = tmp_path / "existing.csv"
    destination.write_text("keep this", encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_group_approval_report_csv(sample_report(), destination)
    assert destination.read_text(encoding="utf-8") == "keep this"


def test_export_does_not_create_missing_parent_directories(tmp_path):
    destination = tmp_path / "missing" / "report.csv"
    with pytest.raises(FileNotFoundError):
        export_group_approval_report_csv(sample_report(), destination)
    assert not destination.exists()


def test_export_does_not_write_audit_events(tmp_path):
    audit.AUDIT_FILE.write_text('original audit content\n', encoding="utf-8")
    before = audit.AUDIT_FILE.read_bytes()
    export_group_approval_report_csv(sample_report(), tmp_path / "report.csv")
    assert audit.AUDIT_FILE.read_bytes() == before
