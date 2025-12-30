"""Tests for standards schema + validation."""

from __future__ import annotations

import json
from pathlib import Path

from motus.standards.validator import StandardsValidator


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_validate_standard_ok(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("MC_VAULT_DIR", str(vault_dir))

    standard_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "type", "version", "applies_if", "output"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "type": {"type": "string", "minLength": 1},
            "version": {"type": "string", "minLength": 1},
            "applies_if": {"type": "object"},
            "output": {"type": "object"},
            "layer": {"type": "string", "enum": ["system", "project", "user"]},
            "status": {"type": "string", "enum": ["active", "deprecated"]},
            "priority": {"type": "integer"},
            "tests": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
        },
    }
    _write_json(
        vault_dir / "core/best-practices/control-plane/standard.schema.json",
        standard_schema,
    )
    _write_json(
        vault_dir / "core/best-practices/control-plane/decision-type.schema.json",
        {"type": "object"},
    )
    _write_json(
        vault_dir / "core/best-practices/control-plane/schemas/color_palette.schema.json",
        {
            "type": "object",
            "required": ["palette"],
            "properties": {"palette": {"type": "string"}},
        },
    )

    registry_path = tmp_path / "decision_types.yaml"
    registry_path.write_text(
        "\n".join(
            [
                "types:",
                "  color_palette:",
                "    required: false",
                "    output_schema: core/best-practices/control-plane/schemas/color_palette.schema.json",
                "    default_slow_path: reason",
                "    context_keys: [artifact, theme]",
                "",
            ]
        ),
        encoding="utf-8",
    )

    standard_path = tmp_path / "standard.yaml"
    standard_path.write_text(
        "\n".join(
            [
                "id: palette.chart.default.light",
                "type: color_palette",
                "version: 1.0.0",
                "applies_if:",
                "  artifact: chart",
                "  theme: light",
                "output:",
                "  palette: motus-default-12",
                "layer: system",
                "status: active",
                "priority: 0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    validator = StandardsValidator()
    result = validator.validate(standard_path, decision_type_registry_path=registry_path)

    assert result.ok is True
    assert result.standard is not None
    assert result.standard.standard_id == "palette.chart.default.light@1.0.0"


def test_validate_standard_missing_required_fields(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("MC_VAULT_DIR", str(vault_dir))

    _write_json(
        vault_dir / "core/best-practices/control-plane/standard.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "type", "version", "applies_if", "output"],
            "properties": {
                "id": {"type": "string"},
                "type": {"type": "string"},
                "version": {"type": "string"},
                "applies_if": {"type": "object"},
                "output": {"type": "object"},
            },
        },
    )

    standard_path = tmp_path / "standard.yaml"
    standard_path.write_text("id: only.id\n", encoding="utf-8")

    validator = StandardsValidator()
    result = validator.validate(standard_path)

    assert result.ok is False
    assert any("required property" in e for e in result.errors)


def test_validate_standard_unknown_predicate_key(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("MC_VAULT_DIR", str(vault_dir))

    _write_json(
        vault_dir / "core/best-practices/control-plane/standard.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["id", "type", "version", "applies_if", "output"],
            "properties": {
                "id": {"type": "string"},
                "type": {"type": "string"},
                "version": {"type": "string"},
                "applies_if": {"type": "object"},
                "output": {"type": "object"},
            },
        },
    )
    _write_json(
        vault_dir / "core/best-practices/control-plane/schemas/color_palette.schema.json",
        {"type": "object"},
    )

    registry_path = tmp_path / "decision_types.yaml"
    registry_path.write_text(
        "\n".join(
            [
                "types:",
                "  color_palette:",
                "    output_schema: core/best-practices/control-plane/schemas/color_palette.schema.json",
                "    context_keys: [artifact]",
                "",
            ]
        ),
        encoding="utf-8",
    )

    standard_path = tmp_path / "standard.yaml"
    standard_path.write_text(
        "\n".join(
            [
                "id: palette.chart.default.light",
                "type: color_palette",
                "version: 1.0.0",
                "applies_if:",
                "  artifact: chart",
                "  theme: light",
                "output:",
                "  palette: motus-default-12",
                "",
            ]
        ),
        encoding="utf-8",
    )

    validator = StandardsValidator()
    result = validator.validate(standard_path, decision_type_registry_path=registry_path)

    assert result.ok is False
    assert any("Unknown predicate key(s)" in e for e in result.errors)


def test_validate_standard_output_schema_violation(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("MC_VAULT_DIR", str(vault_dir))

    _write_json(
        vault_dir / "core/best-practices/control-plane/standard.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["id", "type", "version", "applies_if", "output"],
            "properties": {
                "id": {"type": "string"},
                "type": {"type": "string"},
                "version": {"type": "string"},
                "applies_if": {"type": "object"},
                "output": {"type": "object"},
            },
        },
    )
    _write_json(
        vault_dir / "core/best-practices/control-plane/schemas/color_palette.schema.json",
        {
            "type": "object",
            "required": ["palette"],
            "properties": {"palette": {"type": "string"}},
        },
    )

    registry_path = tmp_path / "decision_types.yaml"
    registry_path.write_text(
        "\n".join(
            [
                "types:",
                "  color_palette:",
                "    output_schema: core/best-practices/control-plane/schemas/color_palette.schema.json",
                "",
            ]
        ),
        encoding="utf-8",
    )

    standard_path = tmp_path / "standard.yaml"
    standard_path.write_text(
        "\n".join(
            [
                "id: palette.chart.default.light",
                "type: color_palette",
                "version: 1.0.0",
                "applies_if:",
                "  artifact: chart",
                "output:",
                "  not_palette: oops",
                "",
            ]
        ),
        encoding="utf-8",
    )

    validator = StandardsValidator()
    result = validator.validate(standard_path, decision_type_registry_path=registry_path)

    assert result.ok is False
    assert any(e.startswith("$.output") for e in result.errors)

