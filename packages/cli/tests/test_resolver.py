from __future__ import annotations

from pathlib import Path

from motus.orient.index import StandardsIndex
from motus.orient.resolver import StandardsResolver


def _write_standard(path: Path, *, standard_id: str, applies_if: dict, output: dict, priority: int = 0) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "standard.yaml").write_text(
        "\n".join(
            [
                f"id: {standard_id}",
                "type: color_palette",
                "version: 1.0.0",
                "applies_if:",
                *[f"  {k}: {v}" for k, v in applies_if.items()],
                f"priority: {priority}",
                "output:",
                *[f"  {k}: {v}" for k, v in output.items()],
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_resolver_specificity_wins(tmp_path: Path):
    motus_dir = tmp_path / ".motus"
    base = motus_dir / "project" / "standards" / "color_palette"

    _write_standard(
        base / "palette.chart.base",
        standard_id="palette.chart.base",
        applies_if={"artifact": "chart"},
        output={"palette": "base"},
    )
    _write_standard(
        base / "palette.chart.dark",
        standard_id="palette.chart.dark",
        applies_if={"artifact": "chart", "theme": "dark"},
        output={"palette": "dark"},
    )

    index = StandardsIndex.build_from_fs(motus_dir)
    resolver = StandardsResolver(index=index)

    hit = resolver.resolve(decision_type="color_palette", context={"artifact": "chart", "theme": "dark"})
    assert hit.result == "HIT"
    assert hit.decision == {"palette": "dark"}


def test_resolver_priority_breaks_tie(tmp_path: Path):
    motus_dir = tmp_path / ".motus"
    base = motus_dir / "project" / "standards" / "color_palette"

    _write_standard(
        base / "palette.chart.p0",
        standard_id="palette.chart.p0",
        applies_if={"artifact": "chart"},
        output={"palette": "p0"},
        priority=0,
    )
    _write_standard(
        base / "palette.chart.p10",
        standard_id="palette.chart.p10",
        applies_if={"artifact": "chart"},
        output={"palette": "p10"},
        priority=10,
    )

    index = StandardsIndex.build_from_fs(motus_dir)
    resolver = StandardsResolver(index=index)

    hit = resolver.resolve(decision_type="color_palette", context={"artifact": "chart"})
    assert hit.result == "HIT"
    assert hit.decision == {"palette": "p10"}


def test_resolver_layer_precedence(tmp_path: Path):
    motus_dir = tmp_path / ".motus"
    user_base = motus_dir / "user" / "standards" / "color_palette"
    system_base = motus_dir / "current" / "system" / "standards" / "color_palette"

    _write_standard(
        system_base / "palette.chart",
        standard_id="palette.chart",
        applies_if={"artifact": "chart", "theme": "dark"},
        output={"palette": "system"},
        priority=0,
    )
    _write_standard(
        user_base / "palette.chart",
        standard_id="palette.chart",
        applies_if={"artifact": "chart"},
        output={"palette": "user"},
        priority=0,
    )

    index = StandardsIndex.build_from_fs(motus_dir)
    resolver = StandardsResolver(index=index)

    # Tie-breaker semantics: more-specific system match beats less-specific user match.
    hit = resolver.resolve(decision_type="color_palette", context={"artifact": "chart", "theme": "dark"})
    assert hit.result == "HIT"
    assert hit.decision == {"palette": "system"}
    assert hit.layer == "system"


def test_resolver_conflict_on_unresolvable(tmp_path: Path):
    motus_dir = tmp_path / ".motus"
    base = motus_dir / "project" / "standards" / "color_palette"

    _write_standard(
        base / "palette.chart.a",
        standard_id="palette.chart.a",
        applies_if={"artifact": "chart"},
        output={"palette": "a"},
        priority=0,
    )
    _write_standard(
        base / "palette.chart.b",
        standard_id="palette.chart.b",
        applies_if={"artifact": "chart"},
        output={"palette": "b"},
        priority=0,
    )

    index = StandardsIndex.build_from_fs(motus_dir)
    resolver = StandardsResolver(index=index)

    conflict = resolver.resolve(decision_type="color_palette", context={"artifact": "chart"})
    assert conflict.result == "CONFLICT"
    assert conflict.candidates is not None
    assert len(conflict.candidates) == 2


def test_resolver_deterministic(tmp_path: Path):
    motus_dir = tmp_path / ".motus"
    base = motus_dir / "project" / "standards" / "color_palette"

    _write_standard(
        base / "palette.chart.dark",
        standard_id="palette.chart.dark",
        applies_if={"artifact": "chart", "theme": "dark"},
        output={"palette": "dark"},
        priority=0,
    )

    index = StandardsIndex.build_from_fs(motus_dir)
    resolver = StandardsResolver(index=index)

    results = [
        resolver.resolve(
            decision_type="color_palette",
            context={"artifact": "chart", "theme": "dark"},
            explain=True,
        ).to_dict(include_trace=True)
        for _ in range(50)
    ]
    assert all(r == results[0] for r in results)
