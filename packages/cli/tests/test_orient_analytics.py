import json
import os
from argparse import Namespace

from motus.commands.orient_cmd import orient_command
from motus.orient.analytics import compute_stats, top_high_miss
from motus.orient.telemetry import orient_events_path


def _ensure_valid_cwd() -> None:
    try:
        os.getcwd()
    except FileNotFoundError:
        os.chdir("/")


def test_compute_stats_hit_miss_conflict():
    events = [
        {"decision_type": "file-naming", "result": "HIT"},
        {"decision_type": "file-naming", "result": "MISS"},
        {"decision_type": "file-naming", "result": "MISS"},
        {"decision_type": "error-format", "result": "MISS"},
        {"decision_type": "error-format", "result": "CONFLICT"},
    ]
    stats = compute_stats(events)

    fn = stats["file-naming"]
    assert fn.calls == 3
    assert fn.hits == 1
    assert fn.misses == 2
    assert fn.conflicts == 0
    assert round(fn.hit_rate, 4) == round(1 / 3, 4)
    assert fn.conflict_rate == 0.0

    ef = stats["error-format"]
    assert ef.calls == 2
    assert ef.hits == 0
    assert ef.misses == 1
    assert ef.conflicts == 1
    assert ef.hit_rate == 0.0
    assert ef.conflict_rate == 0.5


def test_top_high_miss_orders_by_hit_rate():
    events = [
        {"decision_type": "a", "result": "HIT"},
        {"decision_type": "a", "result": "MISS"},
        {"decision_type": "b", "result": "MISS"},
        {"decision_type": "b", "result": "MISS"},
        {"decision_type": "c", "result": "HIT"},
        {"decision_type": "c", "result": "HIT"},
    ]
    stats = compute_stats(events)
    worst = top_high_miss(stats, limit=2, min_calls=1)
    assert [s.decision_type for s in worst] == ["b", "a"]


def test_orient_stats_command_reads_workspace_events(tmp_path, monkeypatch, capsys):
    root = tmp_path / "repo"
    motus_dir = root / ".motus"
    (motus_dir / "state" / "orient").mkdir(parents=True)

    # Mix of HIT/MISS/CONFLICT
    path = orient_events_path(motus_dir)
    payloads = [
        {"ts": "2025-01-01T00:00:00Z", "decision_type": "file-naming", "result": "HIT"},
        {"ts": "2025-01-01T00:00:01Z", "decision_type": "file-naming", "result": "MISS"},
        {"ts": "2025-01-01T00:00:02Z", "decision_type": "error-format", "result": "CONFLICT"},
        {"ts": "2025-01-01T00:00:03Z", "decision_type": "error-format", "result": "MISS"},
    ]
    path.write_text("".join(json.dumps(p) + "\n" for p in payloads), encoding="utf-8")

    _ensure_valid_cwd()
    monkeypatch.chdir(root)

    args = Namespace(
        decision_type="stats",
        high_miss=False,
        min_calls=1,
        stats_path=None,
        json=False,
        # lookup-only args (ignored for stats)
        context=None,
        constraints=None,
        registry=None,
        explain=False,
        rebuild_index=False,
    )
    rc = orient_command(args)
    assert rc == 0

    out = capsys.readouterr().out
    assert "| Type" in out
    assert "file-naming" in out
    assert "error-format" in out


def test_orient_lookup_emits_telemetry(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".motus").mkdir(parents=True)

    _ensure_valid_cwd()
    monkeypatch.chdir(root)

    args = Namespace(
        decision_type="color_palette",
        context="{}",
        constraints=None,
        registry=None,
        explain=False,
        rebuild_index=False,
        # stats-only args (ignored for lookup)
        high_miss=False,
        min_calls=1,
        stats_path=None,
        json=False,
    )
    rc = orient_command(args)
    assert rc == 0

    events_path = orient_events_path(root / ".motus")
    assert events_path.exists()
    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    ev = json.loads(lines[-1])
    assert ev["decision_type"] == "color_palette"
    assert ev["result"] == "MISS"
