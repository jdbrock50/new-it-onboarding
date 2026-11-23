"""Read-only console integration tests for group approval CSV export."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src import console
from src.group_approval import GroupApprovalError


def _report(count=1):
    """A minimal fictional report; no real employee information is used."""
    return SimpleNamespace(
        reviews=tuple(object() for _ in range(count)),
        total_reviews=count,
    )


def test_menu_displays_csv_export_and_exit(capsys):
    console.display_menu()
    output = capsys.readouterr().out
    assert "14. View Group Approval Reporting Dashboard" in output
    assert "15. Export Group Approval Report to CSV" in output
    assert "16. Exit" in output


def test_export_creates_reports_directory_and_calls_service(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    report = _report(2)
    destination = Path("reports") / "audit_group_approval_example.csv"
    with (
        patch.object(console, "generate_group_approval_report", return_value=report) as build,
        patch.object(console, "_audit_report_path", return_value=destination) as path_builder,
        patch.object(console, "export_group_approval_report_csv", return_value=destination) as exporter,
        patch.object(console, "record_audit_event") as audit_writer,
    ):
        console.export_group_approval_reporting_csv()

    assert (tmp_path / "reports").is_dir()
    build.assert_called_once_with()
    path_builder.assert_called_once_with("group_approval")
    exporter.assert_called_once_with(report, destination)
    audit_writer.assert_not_called()
    output = capsys.readouterr().out
    assert "Exported 2 group approval reviews to:" in output
    assert "No group memberships were changed." in output


def test_empty_report_does_not_create_directory_or_export(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with (
        patch.object(console, "generate_group_approval_report", return_value=_report(0)),
        patch.object(console, "export_group_approval_report_csv") as exporter,
        patch.object(console, "record_audit_event") as audit_writer,
    ):
        console.export_group_approval_reporting_csv()
    assert not (tmp_path / "reports").exists()
    exporter.assert_not_called()
    audit_writer.assert_not_called()
    assert "No group approval reviews found. No CSV was created." in capsys.readouterr().out


@pytest.mark.parametrize("error", [
    GroupApprovalError("Invalid audit history"),
    OSError("Audit unavailable"),
    ValueError("Invalid data"),
    TypeError("Invalid structure"),
])
def test_report_generation_failure_skips_export(error, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with (
        patch.object(console, "generate_group_approval_report", side_effect=error),
        patch.object(console, "export_group_approval_report_csv") as exporter,
    ):
        console.export_group_approval_reporting_csv()
    exporter.assert_not_called()
    assert not (tmp_path / "reports").exists()
    output = capsys.readouterr().out
    assert f"Unable to build group approval report ({type(error).__name__})." in output
    assert "Verify the local audit history" in output


@pytest.mark.parametrize("error", [
    OSError("Disk unavailable"),
    ValueError("Invalid destination"),
    TypeError("Invalid report"),
])
def test_export_failure_is_handled(error, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with (
        patch.object(console, "generate_group_approval_report", return_value=_report()),
        patch.object(console, "export_group_approval_report_csv", side_effect=error) as exporter,
        patch.object(console, "record_audit_event") as audit_writer,
    ):
        console.export_group_approval_reporting_csv()
    exporter.assert_called_once()
    audit_writer.assert_not_called()
    assert f"Unable to export group approval report ({type(error).__name__})." in capsys.readouterr().out


def test_directory_creation_failure_is_handled(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reports").write_text("not a directory", encoding="utf-8")
    with (
        patch.object(console, "generate_group_approval_report", return_value=_report()),
        patch.object(console, "export_group_approval_report_csv") as exporter,
    ):
        console.export_group_approval_reporting_csv()
    exporter.assert_not_called()
    assert "Unable to export group approval report (FileExistsError)." in capsys.readouterr().out


def test_menu_option_15_dispatches_and_16_exits_without_extra_pause(capsys):
    with (
        patch.object(console, "display_header"),
        patch.object(console, "display_menu"),
        patch.object(console, "export_group_approval_reporting_csv") as exporter,
        patch("builtins.input", side_effect=["15", "", "16"]) as prompt,
    ):
        console.run_console()
    exporter.assert_called_once_with()
    assert prompt.call_count == 3
    assert "Exiting Shore IT Onboarding." in capsys.readouterr().out


def test_menu_option_16_exits_without_export():
    with (
        patch.object(console, "display_header"),
        patch.object(console, "display_menu"),
        patch.object(console, "export_group_approval_reporting_csv") as exporter,
        patch("builtins.input", return_value="16") as prompt,
    ):
        console.run_console()
    exporter.assert_not_called()
    prompt.assert_called_once()
