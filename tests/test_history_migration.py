"""Tests for migrating onboarding history to stable onboarding IDs."""

import csv
from uuid import UUID

from src import history


LEGACY_FIELDS = [field for field in history.FIELDNAMES if field != "onboarding_id"]


def _legacy_record(name: str, status: str) -> dict[str, str]:
    return {
        "created_at": "2026-10-01T12:00:00+00:00",
        "updated_at": "2026-10-02T12:00:00+00:00",
        "first_name": name,
        "middle_name": "",
        "last_name": "Example",
        "position": "Teacher",
        "program": "Sample Program",
        "location": "Sample Campus",
        "supervisor": "Sample Supervisor",
        "start_date": "2026-11-01",
        "personal_email": f"{name.lower()}@example.com",
        "shore_email": f"{name.lower()}@shorecollaborative.org",
        "devices": "Chromebook",
        "status": status,
    }


def _write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_legacy_migration_preserves_all_fields_and_assigns_unique_ids(
    tmp_path, monkeypatch
):
    path = tmp_path / "onboarding_history.csv"
    monkeypatch.setattr(history, "HISTORY_FILE", path)
    original = [
        _legacy_record("Alex", "Pending"),
        _legacy_record("Jordan", "In Progress"),
        _legacy_record("Taylor", "Completed"),
    ]
    _write_csv(path, LEGACY_FIELDS, original)

    history.ensure_current_schema()

    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        migrated = list(reader)
        assert reader.fieldnames == history.FIELDNAMES

    assert len(migrated) == len(original)
    for before, after in zip(original, migrated, strict=True):
        assert {key: after[key] for key in LEGACY_FIELDS} == before
        assert str(UUID(after["onboarding_id"])) == after["onboarding_id"]
    assert len({row["onboarding_id"] for row in migrated}) == len(migrated)


def test_migration_is_idempotent(tmp_path, monkeypatch):
    path = tmp_path / "onboarding_history.csv"
    monkeypatch.setattr(history, "HISTORY_FILE", path)
    _write_csv(path, LEGACY_FIELDS, [_legacy_record("Alex", "Pending")])

    history.ensure_current_schema()
    first_bytes = path.read_bytes()
    first_records = history.load_onboarding_history()

    history.ensure_current_schema()

    assert path.read_bytes() == first_bytes
    assert history.load_onboarding_history() == first_records


def test_migration_repairs_missing_and_duplicate_ids(tmp_path, monkeypatch):
    path = tmp_path / "onboarding_history.csv"
    monkeypatch.setattr(history, "HISTORY_FILE", path)
    existing_id = "11111111-1111-4111-8111-111111111111"
    rows = [
        {**_legacy_record("Alex", "Pending"), "onboarding_id": existing_id},
        {**_legacy_record("Jordan", "Pending"), "onboarding_id": existing_id},
        {**_legacy_record("Taylor", "Pending"), "onboarding_id": ""},
    ]
    _write_csv(path, history.FIELDNAMES, rows)

    history.ensure_current_schema()
    migrated = history.load_onboarding_history()
    ids = [row["onboarding_id"] for row in migrated]

    assert ids[0] == existing_id
    assert len(set(ids)) == 3
    assert all(str(UUID(value)) == value for value in ids)


def test_missing_history_file_is_not_created(tmp_path, monkeypatch):
    path = tmp_path / "onboarding_history.csv"
    monkeypatch.setattr(history, "HISTORY_FILE", path)

    history.ensure_current_schema()

    assert not path.exists()
