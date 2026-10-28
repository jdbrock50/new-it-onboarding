
"""Tests for the onboarding audit trail."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from src import audit


@pytest.fixture
def audit_file(tmp_path, monkeypatch):
    """Redirect audit storage to a temporary directory."""

    monkeypatch.setattr(audit, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        audit,
        "AUDIT_FILE",
        tmp_path / "onboarding_audit.jsonl",
    )

    return audit.AUDIT_FILE


def test_record_audit_event_creates_file(audit_file):
    """Recording an event creates a valid JSONL file."""

    result = audit.record_audit_event(
        "verification_completed",
        employee_email="jsmith@shorecollaborative.org",
        details={"verified": True},
    )

    assert result == audit_file
    assert audit_file.exists()

    records = audit.load_audit_events()

    assert len(records) == 1
    assert records[0]["event_type"] == "verification_completed"
    assert records[0]["employee_email"] == (
        "jsmith@shorecollaborative.org"
    )
    assert records[0]["details"] == {"verified": True}


def test_audit_event_has_utc_timestamp(audit_file):
    """Audit timestamps include UTC timezone information."""

    audit.record_audit_event(
        "verification_completed",
        employee_email="jsmith@shorecollaborative.org",
    )

    event = audit.load_audit_events()[0]

    timestamp = datetime.fromisoformat(event["timestamp"])

    assert timestamp.tzinfo is not None
    assert timestamp.utcoffset().total_seconds() == 0


def test_audit_events_are_appended(audit_file):
    """Writing another event preserves earlier events."""

    audit.record_audit_event(
        "verification_started",
        employee_email="jsmith@shorecollaborative.org",
    )

    audit.record_audit_event(
        "verification_completed",
        employee_email="jsmith@shorecollaborative.org",
        details={"verified": True},
    )

    events = audit.load_audit_events()

    assert len(events) == 2
    assert events[0]["event_type"] == "verification_started"
    assert events[1]["event_type"] == "verification_completed"

    lines = audit_file.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2

    for line in lines:
        assert isinstance(json.loads(line), dict)


def test_audit_write_failure_raises_error(
    audit_file,
    monkeypatch,
):
    """Storage failures raise AuditWriteError."""

    def fail_mkdir(self, *args, **kwargs):
        raise PermissionError("Permission denied")

    monkeypatch.setattr(
        Path,
        "mkdir",
        fail_mkdir,
    )

    with pytest.raises(
        audit.AuditWriteError,
        match="Unable to save onboarding audit event",
    ):
        audit.record_audit_event(
            "verification_completed",
            employee_email="jsmith@shorecollaborative.org",
        )


def test_load_missing_audit_file_returns_empty(audit_file):
    """Missing audit files return an empty event list."""

    assert not audit_file.exists()
    assert audit.load_audit_events() == []
