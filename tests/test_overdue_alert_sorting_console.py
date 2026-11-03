"""Option 12 priority prompt tests; synthetic data only."""
from unittest.mock import Mock

from src import console


def _report():
    return {"as_of": "2026-11-03", "upcoming_days": 7,
            "counts": {"Overdue": 0, "Due Today": 0, "Upcoming": 0},
            "priority_counts": {"Critical": 0, "High": 0, "Medium": 0, "Low": 0},
            "total_alerts": 0, "errors": [], "alerts": []}


def test_priority_prompt_passed_to_engine(monkeypatch, capsys):
    builder = Mock(return_value=_report())
    monkeypatch.setattr(console, "load_onboarding_history", lambda: [])
    monkeypatch.setattr(console, "build_overdue_alerts", builder)
    answers = iter(["Adult", "Peabody", " High "])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    console.view_overdue_onboarding_alerts()
    assert builder.call_args.kwargs == {"program": "Adult", "location": "Peabody", "priority": "High"}
    assert "Priority filter: High" in capsys.readouterr().out


def test_blank_priority_means_all(monkeypatch, capsys):
    builder = Mock(return_value=_report())
    monkeypatch.setattr(console, "load_onboarding_history", lambda: [])
    monkeypatch.setattr(console, "build_overdue_alerts", builder)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    console.view_overdue_onboarding_alerts()
    assert builder.call_args.kwargs["priority"] is None
    assert "Priority filter: All" in capsys.readouterr().out
