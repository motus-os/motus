# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""OTLP span parser for extracting action context from telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpanAction:
    """Parsed span with extracted action context."""

    trace_id: str
    span_id: str
    name: str
    action_type: str | None
    target: str | None
    provider: str | None
    model: str | None
    safety_score: int | None
    start_time_ns: int
    end_time_ns: int
    raw_attributes: dict[str, Any] = field(default_factory=dict)


def _extract_attribute_value(attr: dict[str, Any]) -> Any:
    """Extract typed value from OTLP attribute value wrapper."""
    value = attr.get("value", {})
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "boolValue" in value:
        return value["boolValue"]
    return None


def _parse_attributes(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    """Parse OTLP attributes list into key-value dict."""
    result = {}
    for attr in attributes:
        key = attr.get("key")
        if key is not None:
            result[key] = _extract_attribute_value(attr)
    return result


def _extract_action_type(name: str) -> str | None:
    """Extract action type from tool.* span names."""
    if not name.startswith("tool."):
        return None
    suffix = name[5:]  # len("tool.") == 5
    return suffix if suffix else None


def _parse_span(span: dict[str, Any]) -> SpanAction:
    """Parse a single OTLP span into SpanAction."""
    attrs = _parse_attributes(span.get("attributes", []))
    name = span.get("name", "")

    return SpanAction(
        trace_id=span.get("traceId", ""),
        span_id=span.get("spanId", ""),
        name=name,
        action_type=_extract_action_type(name),
        target=attrs.get("tool.target"),
        provider=attrs.get("llm.provider"),
        model=attrs.get("llm.model"),
        safety_score=attrs.get("eval.safety_score"),
        start_time_ns=int(span.get("startTimeUnixNano", 0)),
        end_time_ns=int(span.get("endTimeUnixNano", 0)),
        raw_attributes=attrs,
    )


def parse_otlp_spans(payload: dict[str, Any]) -> list[SpanAction]:
    """Parse OTLP JSON payload into list of SpanAction objects.

    Navigates: resourceSpans -> scopeSpans -> spans
    """
    spans = []
    for resource_span in payload.get("resourceSpans", []):
        for scope_span in resource_span.get("scopeSpans", []):
            for span in scope_span.get("spans", []):
                spans.append(_parse_span(span))
    return spans
