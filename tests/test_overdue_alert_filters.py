"""Read-only program/location filtering tests using synthetic employee records."""
from copy import deepcopy
from datetime import date

from src.overdue_alerts import build_overdue_alerts

TODAY = date(2026, 11, 3)


def record(ident, program, location, start_date="2026-11-01", status="Pending"):
    return {
        "first_name": "Test", "middle_name": "", "last_name": ident,
        "position": "Teacher", "program": program, "location": location,
        "supervisor": "Example", "start_date": start_date,
        "personal_email": f"{ident}@example.invalid",
        "shore_email": f"{ident}@example.invalid", "devices": "None",
        "status": status, "onboarding_id": ident,
    }


def sample():
    return [
        record("one", "Adult Program", "Peabody"),
        record("two", "Adult Program", "Woburn", "2026-11-03"),
        record("three", "Elementary", "Peabody", "2026-11-06"),
        record("four", "Elementary", "Chelsea", "2026-11-01"),
    ]


def build(records, tmp_path, **filters):
    return build_overdue_alerts(records, progress_path=tmp_path / "missing.json", today=TODAY, **filters)


def test_unfiltered_preserves_all_alerts(tmp_path):
    result = build(sample(), tmp_path)
    assert result["total_alerts"] == 4
    assert result["counts"] == {"Overdue": 2, "Due Today": 1, "Upcoming": 1}


def test_filter_by_program(tmp_path):
    result = build(sample(), tmp_path, program="Adult Program")
    assert {item["onboarding_id"] for item in result["alerts"]} == {"one", "two"}
    assert result["counts"] == {"Overdue": 1, "Due Today": 1, "Upcoming": 0}


def test_filter_by_location(tmp_path):
    result = build(sample(), tmp_path, location="Peabody")
    assert {item["onboarding_id"] for item in result["alerts"]} == {"one", "three"}


def test_combined_filters(tmp_path):
    result = build(sample(), tmp_path, program="Adult Program", location="Woburn")
    assert [item["onboarding_id"] for item in result["alerts"]] == ["two"]


def test_filters_ignore_case_and_outer_whitespace(tmp_path):
    result = build(sample(), tmp_path, program="  adult program ", location="  PEABODY  ")
    assert [item["onboarding_id"] for item in result["alerts"]] == ["one"]


def test_blank_filters_mean_all(tmp_path):
    result = build(sample(), tmp_path, program="  ", location="")
    assert result["total_alerts"] == 4


def test_unmatched_filters_return_empty_counts(tmp_path):
    result = build(sample(), tmp_path, program="No such program")
    assert result["alerts"] == []
    assert result["counts"] == {"Overdue": 0, "Due Today": 0, "Upcoming": 0}
    assert result["errors"] == []


def test_alerts_include_program_and_location(tmp_path):
    result = build(sample(), tmp_path, program="Adult Program", location="Peabody")
    assert result["alerts"][0]["program"] == "Adult Program"
    assert result["alerts"][0]["location"] == "Peabody"


def test_filtering_does_not_mutate_records_or_write_progress(tmp_path):
    records = sample()
    original = deepcopy(records)
    progress = tmp_path / "missing.json"
    build_overdue_alerts(records, progress_path=progress, today=TODAY, location="Peabody")
    assert records == original
    assert not progress.exists()


def test_filtered_out_invalid_record_does_not_generate_error(tmp_path):
    records = sample() + [record("broken", "Other", "Other", start_date="invalid")]
    result = build(records, tmp_path, program="Adult Program")
    assert result["errors"] == []
    assert result["total_alerts"] == 2
