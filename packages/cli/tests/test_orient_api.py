"""Tests for Cached Orient API surface (v0)."""

from __future__ import annotations

from typing import Any

from motus.orient.api import OrientAPI
from motus.orient.fs_resolver import FilesystemStandardsResolverV0
from motus.orient.result import OrientResult
from motus.standards.schema import DecisionType, DecisionTypeRegistry


def test_orient_miss_defaults_to_allowed():
    api = OrientAPI()
    result = api.orient("color_palette", {"artifact": "chart"})
    assert result.result == "MISS"
    assert result.slow_path == "allowed"


def test_orient_miss_required_type_sets_required_slow_path():
    registry = DecisionTypeRegistry(
        types={
            "file_layout": DecisionType(
                name="file_layout",
                required=True,
                output_schema=None,
                default_slow_path="reason",
                context_keys=None,
            )
        }
    )
    api = OrientAPI(decision_types=registry)
    result = api.orient("file_layout", {"artifact": "repo"})
    assert result.result == "MISS"
    assert result.slow_path == "required"


def test_orient_miss_block_default_sets_blocked_slow_path():
    registry = DecisionTypeRegistry(
        types={
            "color_palette": DecisionType(
                name="color_palette",
                required=False,
                output_schema=None,
                default_slow_path="block",
                context_keys=None,
            )
        }
    )
    api = OrientAPI(decision_types=registry)
    result = api.orient("color_palette", {"artifact": "chart"})
    assert result.result == "MISS"
    assert result.slow_path == "blocked"


def test_orient_passes_through_hit_from_resolver():
    class FakeResolver:
        def resolve(
            self,
            *,
            decision_type: str,
            context: dict[str, Any],
            constraints: dict[str, Any] | None = None,
            explain: bool = False,
        ) -> OrientResult:
            _ = (decision_type, context, constraints, explain)
            return OrientResult(
                result="HIT",
                decision={"palette": "motus-default-12"},
                standard_id="palette.chart.default.light@1.0.0",
                layer="system",
            )

    api = OrientAPI(resolver=FakeResolver())
    result = api.orient("color_palette", {"artifact": "chart"})
    assert result.result == "HIT"
    assert result.decision == {"palette": "motus-default-12"}


def test_orient_result_serialization_contract():
    hit = OrientResult(
        result="HIT",
        decision={"palette": "x"},
        standard_id="s@1.0.0",
        layer="system",
        match_trace={"note": "ok"},
    )
    assert hit.to_dict(include_trace=False) == {
        "decision": {"palette": "x"},
        "layer": "system",
        "result": "HIT",
        "standard_id": "s@1.0.0",
    }
    assert hit.to_dict(include_trace=True)["match_trace"] == {"note": "ok"}

    miss = OrientResult(result="MISS", slow_path="allowed", match_trace={"note": "miss"})
    assert miss.to_dict(include_trace=False) == {"result": "MISS", "slow_path": "allowed"}
    assert miss.to_dict(include_trace=True)["match_trace"] == {"note": "miss"}

    conflict = OrientResult(result="CONFLICT", candidates=[{"id": "a"}, {"id": "b"}])
    assert conflict.to_dict(include_trace=False) == {
        "candidates": [{"id": "a"}, {"id": "b"}],
        "result": "CONFLICT",
    }


def test_filesystem_resolver_hit_and_conflict(tmp_path):
    motus_dir = tmp_path / ".motus"
    user_dir = motus_dir / "user" / "standards" / "color_palette" / "palette.chart.default.light"
    project_dir = (
        motus_dir / "project" / "standards" / "color_palette" / "palette.chart.default.light.2"
    )

    user_dir.mkdir(parents=True)
    project_dir.mkdir(parents=True)

    (user_dir / "standard.yaml").write_text(
        "\n".join(
            [
                "id: palette.chart.default.light",
                "type: color_palette",
                "version: 1.0.0",
                "applies_if:",
                "  artifact: chart",
                "  theme: light",
                "output:",
                "  palette: user-palette",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (project_dir / "standard.yaml").write_text(
        "\n".join(
            [
                "id: palette.chart.default.light.2",
                "type: color_palette",
                "version: 1.0.0",
                "applies_if:",
                "  artifact: chart",
                "  theme: dark",
                "output:",
                "  palette: project-palette",
                "",
            ]
        ),
        encoding="utf-8",
    )

    resolver = FilesystemStandardsResolverV0(motus_dir=motus_dir)
    api = OrientAPI(resolver=resolver)

    # Same specificity + priority => user layer wins.
    hit = api.orient("color_palette", {"artifact": "chart", "theme": "light"})
    assert hit.result == "HIT"
    assert hit.decision == {"palette": "user-palette"}
    assert hit.layer == "user"

    # Conflict when multiple match in the same highest-precedence layer.
    project_dir2 = (
        motus_dir / "project" / "standards" / "color_palette" / "palette.chart.default.light.3"
    )
    project_dir2.mkdir(parents=True)
    (project_dir2 / "standard.yaml").write_text(
        "\n".join(
            [
                "id: palette.chart.default.light.3",
                "type: color_palette",
                "version: 1.0.0",
                "applies_if:",
                "  artifact: chart",
                "  theme: dark",
                "priority: 0",
                "output:",
                "  palette: project-palette-2",
                "",
            ]
        ),
        encoding="utf-8",
    )

    conflict = api.orient("color_palette", {"artifact": "chart", "theme": "dark"})
    assert conflict.result == "CONFLICT"
