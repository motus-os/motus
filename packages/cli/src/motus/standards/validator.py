# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Standards validation against JSON Schema + decision type constraints."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from motus.config import config
from motus.standards.schema import DecisionTypeRegistry, Standard


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...] = ()
    standard: Standard | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "standard_id": self.standard.standard_id if self.standard else None,
            "type": self.standard.type if self.standard else None,
            "layer": self.standard.layer if self.standard else None,
        }


def _error_path(e: jsonschema.ValidationError) -> str:
    if not e.absolute_path:
        return "$"
    return "$." + ".".join(str(p) for p in e.absolute_path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class StandardsValidator:
    """Validate standard.yaml files.

    This validator is intentionally strict and returns clear, stable error strings.
    """

    def __init__(self, vault_dir: Path | None = None) -> None:
        self._vault_dir = vault_dir or config.paths.vault_dir

    def _schema_path(self, filename: str) -> Path:
        if self._vault_dir is None:
            raise ValueError(
                "Vault directory is not configured (set MC_VAULT_DIR or pass --vault-dir)"
            )
        return self._vault_dir / "core" / "best-practices" / "control-plane" / filename

    def _validate_jsonschema(self, schema: dict[str, Any], data: Any) -> list[str]:
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: (list(e.absolute_path), e.message))
        rendered: list[str] = []
        for e in errors:
            rendered.append(f"{_error_path(e)}: {e.message}")
        return rendered

    def validate(
        self,
        standard_path: str | Path,
        *,
        decision_type_registry_path: str | Path | None = None,
    ) -> ValidationResult:
        p = Path(standard_path).expanduser()
        try:
            raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        except OSError as e:
            return ValidationResult(ok=False, errors=(f"Failed to read standard: {e}",))
        except yaml.YAMLError as e:
            return ValidationResult(ok=False, errors=(f"Failed to parse YAML: {e}",))

        if not isinstance(raw, dict):
            return ValidationResult(ok=False, errors=("Standard YAML must be a mapping",))

        errors: list[str] = []

        # 1) Validate base schema (structure + required fields)
        try:
            standard_schema = _load_json(self._schema_path("standard.schema.json"))
        except (OSError, ValueError, json.JSONDecodeError) as e:
            return ValidationResult(ok=False, errors=(f"Failed to load standard schema: {e}",))

        errors.extend(self._validate_jsonschema(standard_schema, raw))

        # If schema fails, avoid cascading errors from parsing into dataclass.
        if errors:
            return ValidationResult(ok=False, errors=tuple(errors))

        standard = Standard(
            id=str(raw["id"]),
            type=str(raw["type"]),
            version=str(raw["version"]),
            applies_if=dict(raw.get("applies_if") or {}),
            output=dict(raw.get("output") or {}),
            layer=str(raw.get("layer") or "project"),  # validated by schema
            status=str(raw.get("status") or "active"),  # validated by schema
            priority=int(raw.get("priority") or 0),
            tests=list(raw.get("tests") or []) or None,
            rationale=(str(raw["rationale"]) if "rationale" in raw and raw["rationale"] is not None else None),
        )

        # 2) Decision type registry-driven validations (optional, but recommended)
        registry: DecisionTypeRegistry | None = None
        if decision_type_registry_path is not None:
            try:
                registry = DecisionTypeRegistry.load(decision_type_registry_path)
            except Exception as e:
                return ValidationResult(
                    ok=False,
                    errors=(f"Failed to load decision type registry: {e}",),
                )

        if registry is not None:
            dt = registry.get(standard.type)
            if dt is None:
                errors.append(f"Unknown decision type: {standard.type}")
            else:
                if dt.context_keys is not None:
                    unknown = sorted(set(standard.applies_if.keys()) - set(dt.context_keys))
                    if unknown:
                        errors.append(
                            f"Unknown predicate key(s) for type '{standard.type}': {', '.join(unknown)}"
                        )

                if dt.output_schema:
                    schema_path = Path(dt.output_schema).expanduser()
                    if not schema_path.is_absolute():
                        # Treat as vault-relative when possible.
                        if self._vault_dir is not None:
                            schema_path = (self._vault_dir / schema_path).resolve()
                        else:
                            schema_path = (Path.cwd() / schema_path).resolve()
                    try:
                        output_schema = _load_json(schema_path)
                    except (OSError, json.JSONDecodeError) as e:
                        errors.append(f"Failed to load output schema '{schema_path}': {e}")
                    else:
                        output_errors = self._validate_jsonschema(output_schema, standard.output)
                        errors.extend([f"$.output{msg[1:]}" for msg in output_errors])

        if errors:
            return ValidationResult(ok=False, errors=tuple(errors), standard=standard)

        return ValidationResult(ok=True, standard=standard)

