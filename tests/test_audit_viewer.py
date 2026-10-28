"""Tests for the read-only onboarding audit log viewer."""

import json

from src import audit, console


def _event(number: int) -> dict[str, object]:
    return {
        "timestamp": f"2026-10-28T10:{number:02d}:00+00:00",
        "event_type": "verification_completed",
        "employee_email": f"employee{number}@shorecollaborative.org",
        "details": {"verification_complete": True},
    }


def test_missing_audit_log_displays_empty_message(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(audit, "AUDIT_FILE", tmp_path / "missing.jsonl")

    console.view_audit_log()

    output = capsys.readouterr().out
    assert "AUDIT LOG" in output
    assert "No audit events found." in output


def test_viewer_displays_recent_events_newest_first(monkeypatch, tmp_path, capsys):
    path = tmp_path / "audit.jsonl"
    path.write_text(
        "\n".join(json.dumps(_event(n)) for n in range(1, 4)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "AUDIT_FILE", path)

    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    console.view_audit_log()

    output = capsys.readouterr().out
    assert output.index("employee3@") < output.index("employee2@")
    assert output.index("employee2@") < output.index("employee1@")
    assert "verification_completed" in output
    assert "2026-10-28T10:03:00+00:00" in output


def test_viewer_limits_display_to_twenty_events(monkeypatch, tmp_path, capsys):
    path = tmp_path / "audit.jsonl"
    path.write_text(
        "\n".join(json.dumps(_event(n)) for n in range(1, 26)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "AUDIT_FILE", path)

    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    console.view_audit_log()

    output = capsys.readouterr().out
    assert "employee25@" in output
    assert "employee6@" in output
    assert "employee5@" not in output
    assert output.count("   Event: ") == 20


def test_viewer_reports_invalid_json_without_crashing(monkeypatch, tmp_path, capsys):
    path = tmp_path / "audit.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    monkeypatch.setattr(audit, "AUDIT_FILE", path)

    console.view_audit_log()

    assert "Unable to read audit log" in capsys.readouterr().out


def test_viewer_does_not_change_audit_file(monkeypatch, tmp_path):
    path = tmp_path / "audit.jsonl"
    original = json.dumps(_event(1)) + "\n"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(audit, "AUDIT_FILE", path)

    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    console.view_audit_log()

    assert path.read_text(encoding="utf-8") == original


def test_viewer_filters_by_email(monkeypatch, tmp_path, capsys):
    path = tmp_path / "audit.jsonl"
    path.write_text(
        "\n".join(json.dumps(_event(n)) for n in range(1, 4)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "AUDIT_FILE", path)
    answers = iter(["EMPLOYEE2", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    console.view_audit_log()

    output = capsys.readouterr().out
    assert "employee2@" in output
    assert "employee1@" not in output
    assert "employee3@" not in output
    assert "Matching events: 1" in output


def test_viewer_filters_by_event_type(monkeypatch, tmp_path, capsys):
    path = tmp_path / "audit.jsonl"
    first = _event(1)
    second = _event(2)
    second["event_type"] = "override_approved"
    path.write_text(
        json.dumps(first) + "\n" + json.dumps(second) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "AUDIT_FILE", path)
    answers = iter(["", "OVERRIDE_APPROVED", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    console.view_audit_log()

    output = capsys.readouterr().out
    assert "employee2@" in output
    assert "employee1@" not in output
    assert "Matching events: 1" in output


def test_viewer_reports_no_matching_events(monkeypatch, tmp_path, capsys):
    path = tmp_path / "audit.jsonl"
    path.write_text(json.dumps(_event(1)) + "\n", encoding="utf-8")
    monkeypatch.setattr(audit, "AUDIT_FILE", path)
    answers = iter(["not-present", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    console.view_audit_log()

    assert "No matching audit events found." in capsys.readouterr().out


def test_viewer_filters_by_inclusive_date_range(monkeypatch, tmp_path, capsys):
    path = tmp_path / "audit.jsonl"
    events = [_event(n) for n in range(1, 4)]
    events[0]["timestamp"] = "2026-10-01T08:00:00+00:00"
    events[1]["timestamp"] = "2026-10-15T08:00:00+00:00"
    events[2]["timestamp"] = "2026-10-31T08:00:00+00:00"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    monkeypatch.setattr(audit, "AUDIT_FILE", path)
    answers = iter(["", "", "2026-10-01", "2026-10-15"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    console.view_audit_log()

    output = capsys.readouterr().out
    assert "employee1@" in output
    assert "employee2@" in output
    assert "employee3@" not in output
    assert "Matching events: 2" in output


def test_viewer_combines_email_type_and_dates(monkeypatch, tmp_path, capsys):
    path = tmp_path / "audit.jsonl"
    events = [_event(n) for n in range(1, 4)]
    events[0]["timestamp"] = "2026-09-30T10:00:00+00:00"
    events[1]["timestamp"] = "2026-10-10T10:00:00+00:00"
    events[1]["event_type"] = "override_approved"
    events[2]["timestamp"] = "2026-10-11T10:00:00+00:00"
    events[2]["event_type"] = "override_approved"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    monkeypatch.setattr(audit, "AUDIT_FILE", path)
    answers = iter(["employee2", "OVERRIDE_APPROVED", "2026-10-01", "2026-10-31"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    console.view_audit_log()

    output = capsys.readouterr().out
    assert "employee2@" in output
    assert "employee1@" not in output
    assert "employee3@" not in output
    assert "Matching events: 1" in output


def test_viewer_reports_invalid_date(monkeypatch, tmp_path, capsys):
    path = tmp_path / "audit.jsonl"
    path.write_text(json.dumps(_event(1)) + "\n", encoding="utf-8")
    monkeypatch.setattr(audit, "AUDIT_FILE", path)
    answers = iter(["", "", "2026-13-01", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    console.view_audit_log()

    assert "Invalid audit search:" in capsys.readouterr().out


def test_viewer_reports_reversed_date_range(monkeypatch, tmp_path, capsys):
    path = tmp_path / "audit.jsonl"
    path.write_text(json.dumps(_event(1)) + "\n", encoding="utf-8")
    monkeypatch.setattr(audit, "AUDIT_FILE", path)
    answers = iter(["", "", "2026-10-31", "2026-10-01"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    console.view_audit_log()

    output = capsys.readouterr().out
    assert "Invalid audit search:" in output
    assert "Start date cannot be after end date." in output
