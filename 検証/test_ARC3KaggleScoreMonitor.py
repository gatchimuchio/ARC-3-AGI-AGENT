from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MONITOR_PATH = ROOT / "運用/ARC26-UNIFIED/ARC3_Kaggleスコア監視.py"
SPEC = importlib.util.spec_from_file_location("arc3_kaggle_score_monitor", MONITOR_PATH)
assert SPEC and SPEC.loader
MONITOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MONITOR)


def test_pending_schedule_steps_up_without_shortening_later_checks():
    assert [MONITOR._pending_interval_minutes(n) for n in range(1, 6)] == [5, 15, 30, 60, 60]


def test_empty_score_stays_unobserved_and_zero_is_numeric():
    assert MONITOR._numeric_score("") is None
    assert MONITOR._numeric_score(None) is None
    assert MONITOR._numeric_score("0.00") == 0
    assert MONITOR._score_delta("", "0.25") is None
    assert MONITOR._score_delta("0.00", "0.25") == -0.25


def test_due_gate_skips_network_until_due_and_force_only_overrides_gate():
    now = datetime(2026, 10, 24, 10, tzinfo=timezone.utc)
    due = now + timedelta(minutes=15)
    assert MONITOR._due_record(now, due, force=False)["state"] == "not_due"
    assert MONITOR._due_record(now, due, force=True) is None
    assert MONITOR._due_record(due, due, force=False) is None


def test_cli_prefix_uses_the_pinned_kaggle_release(monkeypatch):
    monkeypatch.setattr(MONITOR, "ROOT", Path(__file__).resolve().parent)
    monkeypatch.setattr(MONITOR.shutil, "which", lambda name: r"C:\tools\uvx.exe" if name == "uvx" else None)

    assert MONITOR._cli_prefix() == [r"C:\tools\uvx.exe", "--from", "kaggle==2.2.5", "kaggle"]


def test_cli_prefix_prefers_manifest_pinned_project_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(MONITOR, "ROOT", tmp_path)
    manifest = tmp_path / "運用" / "ARC26-UNIFIED" / "kaggle-cli-environment.json"
    manifest.parent.mkdir(parents=True)
    venv = tmp_path / "project-kaggle-env"
    cli = venv / "Scripts" / "kaggle.exe"
    cli.parent.mkdir(parents=True)
    cli.write_bytes(b"pinned project cli")
    manifest.write_text(
        json.dumps({
            "track": "ARC3",
            "kaggle_cli": "Kaggle CLI 2.2.5",
            "venv_path": str(venv),
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(MONITOR.shutil, "which", lambda name: r"C:\tools\uvx.exe" if name == "uvx" else None)

    assert MONITOR._cli_prefix() == [str(cli)]


def test_history_parser_ignores_kaggle_cli_version_notice(monkeypatch):
    row = {
        "ref": 57577905,
        "date": "2026-10-24T10:48:04.000Z",
        "status": "SubmissionStatus.COMPLETE",
        "publicScore": "23.86",
    }
    warning = (
        "Warning: Looks like you're using an outdated `kaggle` version "
        "(installed: 2.2.4), please consider upgrading to the latest version (2.2.5)\n"
    )
    output = warning + json.dumps([row])
    monkeypatch.setattr(MONITOR, "_run_cli", lambda arguments: SimpleNamespace(stdout=output))

    assert MONITOR._fetch_history() == [row]
