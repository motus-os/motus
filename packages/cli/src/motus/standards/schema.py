# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Dataclasses for standards and decision type registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

SlowPathDefault = Literal["reason", "block", "fallback"]


@dataclass(frozen=True, slots=True)
class Standard:
    """A typed cached decision (a "standard")."""

    id: str
    type: str
    version: str
    applies_if: dict[str, Any]
    output: dict[str, Any]
    layer: Literal["system", "project", "user"] = "project"
    status: Literal["active", "deprecated"] = "active"
    priority: int = 0
    tests: list[str] | None = None
    rationale: str | None = None

    @property
    def standard_id(self) -> str:
        return f"{self.id}@{self.version}"


@dataclass(frozen=True, slots=True)
class DecisionType:
    """Definition of a decision type for Cached Orient."""

    name: str
    required: bool = False
    output_schema: str | None = None
    default_slow_path: SlowPathDefault = "reason"
    context_keys: frozenset[str] | None = None


@dataclass(frozen=True, slots=True)
class DecisionTypeRegistry:
    """Loaded registry of decision types."""

    types: dict[str, DecisionType]

    def get(self, name: str) -> DecisionType | None:
        return self.types.get(name)

    @classmethod
    def load(cls, path: str | Path) -> DecisionTypeRegistry:
        p = Path(path).expanduser()
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Decision type registry must be a mapping at top-level")

        raw_types = raw.get("types")
        if not isinstance(raw_types, dict):
            raise ValueError("Decision type registry must contain a 'types' mapping")

        parsed: dict[str, DecisionType] = {}
        for type_name, spec in raw_types.items():
            if not isinstance(type_name, str) or not type_name:
                raise ValueError("Decision type names must be non-empty strings")
            if not isinstance(spec, dict):
                raise ValueError(f"Decision type '{type_name}' must be a mapping")

            required = bool(spec.get("required", False))
            output_schema = spec.get("output_schema")
            if output_schema is not None and not isinstance(output_schema, str):
                raise ValueError(f"Decision type '{type_name}': output_schema must be a string")

            default_slow_path = spec.get("default_slow_path", "reason")
            if default_slow_path not in ("reason", "block", "fallback"):
                raise ValueError(
                    f"Decision type '{type_name}': default_slow_path must be one of "
                    "'reason'|'block'|'fallback'"
                )

            raw_context_keys = spec.get("context_keys", None)
            context_keys: frozenset[str] | None = None
            if raw_context_keys is not None:
                if not isinstance(raw_context_keys, list) or not all(
                    isinstance(k, str) and k for k in raw_context_keys
                ):
                    raise ValueError(
                        f"Decision type '{type_name}': context_keys must be a list of strings"
                    )
                context_keys = frozenset(raw_context_keys)

            parsed[type_name] = DecisionType(
                name=type_name,
                required=required,
                output_schema=output_schema,
                default_slow_path=default_slow_path,
                context_keys=context_keys,
            )

        return cls(types=parsed)

