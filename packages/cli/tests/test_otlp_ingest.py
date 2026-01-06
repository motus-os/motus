"""Tests for OTLP ingest module - parser, bridge, and endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from motus.ingest.bridge import process_span_action
from motus.ingest.otlp import OTLPIngestApp, create_app
from motus.ingest.parser import SpanAction, parse_otlp_spans


@pytest.fixture(autouse=True)
def _unset_vault_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MC_VAULT_DIR", raising=False)


@pytest.fixture
def sample_otlp_payload():
    """Standard OTLP payload with tool and non-tool spans."""
    return {
        "resourceSpans": [{
            "scopeSpans": [{
                "spans": [
                    {
                        "traceId": "abc123",
                        "spanId": "span1",
                        "name": "tool.file_write",
                        "startTimeUnixNano": "1000000000",
                        "endTimeUnixNano": "1000100000",
                        "attributes": [
                            {"key": "tool.target", "value": {"stringValue": "/tmp/test.txt"}},
                            {"key": "llm.provider", "value": {"stringValue": "anthropic"}},
                        ],
                    },
                    {
                        "traceId": "abc123",
                        "spanId": "span2",
                        "name": "llm.completion",
                        "startTimeUnixNano": "1000000000",
                        "endTimeUnixNano": "1000050000",
                        "attributes": [],
                    },
                ],
            }],
        }],
    }


@pytest.fixture
def test_client():
    """FastAPI test client for endpoint tests."""
    return TestClient(create_app())


def _make_span(name, trace_id="t1", span_id="s1", safety_score=None, target=None):
    """Helper to create SpanAction for tests."""
    return SpanAction(
        trace_id=trace_id, span_id=span_id, name=name,
        action_type=name.split(".", 1)[1] if name.startswith("tool.") else None,
        target=target, provider="anthropic", model="claude-3",
        safety_score=safety_score, start_time_ns=0, end_time_ns=0, raw_attributes={},
    )


# Parser Tests

def test_parser_extracts_multiple_spans(sample_otlp_payload):
    """parse_otlp_spans extracts all spans from payload."""
    spans = parse_otlp_spans(sample_otlp_payload)
    assert len(spans) == 2
    assert spans[0].span_id == "span1"
    assert spans[1].span_id == "span2"


def test_parser_extracts_attributes(sample_otlp_payload):
    """Parser correctly extracts tool.target and llm.provider attributes."""
    spans = parse_otlp_spans(sample_otlp_payload)
    assert spans[0].target == "/tmp/test.txt"
    assert spans[0].provider == "anthropic"
    assert spans[0].action_type == "file_write"


def test_parser_handles_integer_attributes():
    """Parser correctly handles intValue attribute types."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "t", "spanId": "s", "name": "tool.test",
        "startTimeUnixNano": "0", "endTimeUnixNano": "0",
        "attributes": [{"key": "eval.safety_score", "value": {"intValue": "750"}}],
    }]}]}]}
    spans = parse_otlp_spans(payload)
    assert spans[0].safety_score == 750


def test_parser_handles_missing_attributes():
    """Parser handles spans without attributes array."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "t", "spanId": "s", "name": "test.span",
        "startTimeUnixNano": "0", "endTimeUnixNano": "0",
    }]}]}]}
    spans = parse_otlp_spans(payload)
    assert len(spans) == 1
    assert spans[0].raw_attributes == {}


def test_parser_handles_empty_resource_spans():
    """Parser handles empty resourceSpans array."""
    assert parse_otlp_spans({"resourceSpans": []}) == []
    assert parse_otlp_spans({}) == []


def test_parser_handles_malformed_input():
    """Parser handles various malformed inputs gracefully."""
    assert parse_otlp_spans({"resourceSpans": [{"scopeSpans": []}]}) == []
    assert parse_otlp_spans({"resourceSpans": [{}]}) == []


# Bridge Tests

def test_bridge_tool_spans_get_gated():
    """Tool spans are processed through gates."""
    span = _make_span("tool.bash", safety_score=800)
    decision = process_span_action(span)
    assert decision.decision in ("permit", "deny")
    assert decision.evidence_id is not None


def test_bridge_non_tool_spans_pass_through():
    """Non-tool spans pass through without gating."""
    span = _make_span("llm.completion")
    decision = process_span_action(span)
    assert decision.decision == "pass"
    assert decision.reason == "not_a_tool"
    assert decision.evidence_id is None


def test_bridge_low_safety_score_triggers_deny():
    """Low safety score (< 500) denies the action."""
    span = _make_span("tool.exec", safety_score=300)
    decision = process_span_action(span)
    assert decision.decision == "deny"
    assert "safety_score_below_threshold:300" in decision.reason


def test_bridge_high_safety_score_permits():
    """High safety score (>= 500) permits the action."""
    span = _make_span("tool.read", safety_score=800)
    decision = process_span_action(span)
    assert decision.decision == "permit"
    assert decision.evidence_id.startswith("ev-")


def test_bridge_evidence_id_generated_for_gated_spans():
    """Evidence ID is generated for both permit and deny decisions."""
    permit_span = _make_span("tool.a", safety_score=800)
    deny_span = _make_span("tool.b", safety_score=100)
    assert process_span_action(permit_span).evidence_id is not None
    assert process_span_action(deny_span).evidence_id is not None


# Endpoint Tests

def test_endpoint_post_traces_accepts_valid_otlp(test_client, sample_otlp_payload):
    """POST /v1/traces accepts valid OTLP JSON."""
    response = test_client.post("/v1/traces", json=sample_otlp_payload)
    assert response.status_code == 200


def test_endpoint_returns_correct_structure(test_client, sample_otlp_payload):
    """Response contains received, processed, results with correct counts."""
    data = test_client.post("/v1/traces", json=sample_otlp_payload).json()
    assert data["received"] == 2
    assert data["processed"] == 2
    assert len(data["results"]) == 2
    for r in data["results"]:
        assert all(k in r for k in ("trace_id", "span_id", "decision", "latency_ms"))


def test_endpoint_health_returns_200(test_client):
    """GET /health returns 200 OK."""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_endpoint_invalid_json_returns_400(test_client):
    """POST /v1/traces with invalid JSON returns 400."""
    response = test_client.post("/v1/traces", content="not json",
                                headers={"Content-Type": "application/json"})
    assert response.status_code == 400


def test_endpoint_empty_body_handled(test_client):
    """POST /v1/traces with empty payload returns 200 with zero spans."""
    data = test_client.post("/v1/traces", json={}).json()
    assert data["received"] == 0
    assert data["results"] == []


# Integration Tests

def test_integration_full_flow(test_client):
    """Full flow: OTLP JSON -> parse -> gate -> response."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "int-trace", "spanId": "int-span", "name": "tool.read",
        "startTimeUnixNano": "0", "endTimeUnixNano": "0",
        "attributes": [{"key": "eval.safety_score", "value": {"intValue": "900"}}],
    }]}]}]}
    data = test_client.post("/v1/traces", json=payload).json()
    assert data["received"] == 1
    assert data["results"][0]["decision"] == "permit"
    assert data["results"][0]["evidence_id"] is not None


def test_integration_multiple_spans_single_request(test_client):
    """Multiple spans in single request are all processed."""
    spans = [{"traceId": "t", "spanId": f"s{i}", "name": f"tool.op{i}",
              "startTimeUnixNano": "0", "endTimeUnixNano": "0", "attributes": []}
             for i in range(3)]
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}
    data = test_client.post("/v1/traces", json=payload).json()
    assert data["received"] == 3
    assert data["processed"] == 3


def test_integration_mixed_tool_and_non_tool_spans(test_client, sample_otlp_payload):
    """Mixed tool/non-tool spans get appropriate decisions."""
    data = test_client.post("/v1/traces", json=sample_otlp_payload).json()
    decisions = {r["span_id"]: r["decision"] for r in data["results"]}
    assert decisions["span1"] in ("permit", "deny")  # tool.file_write
    assert decisions["span2"] == "pass"  # llm.completion


def test_integration_create_app():
    """create_app and OTLPIngestApp correctly create FastAPI app."""
    from fastapi import FastAPI
    assert isinstance(create_app(), FastAPI)
    ingest = OTLPIngestApp()
    routes = [r.path for r in ingest.app.routes]
    assert "/health" in routes and "/v1/traces" in routes


# Edge Case Tests

def test_parser_boundary_safety_score_499():
    """Safety score 499 (just below threshold) triggers deny."""
    span = _make_span("tool.exec", safety_score=499)
    decision = process_span_action(span)
    assert decision.decision == "deny"


def test_parser_boundary_safety_score_500():
    """Safety score 500 (exactly at threshold) permits."""
    span = _make_span("tool.exec", safety_score=500)
    decision = process_span_action(span)
    assert decision.decision == "permit"


def test_parser_handles_double_attributes():
    """Parser correctly handles doubleValue attribute types."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "t", "spanId": "s", "name": "llm.completion",
        "startTimeUnixNano": "0", "endTimeUnixNano": "0",
        "attributes": [{"key": "latency", "value": {"doubleValue": 123.456}}],
    }]}]}]}
    spans = parse_otlp_spans(payload)
    assert spans[0].raw_attributes["latency"] == 123.456


def test_parser_handles_bool_attributes():
    """Parser correctly handles boolValue attribute types."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "t", "spanId": "s", "name": "tool.test",
        "startTimeUnixNano": "0", "endTimeUnixNano": "0",
        "attributes": [{"key": "cached", "value": {"boolValue": True}}],
    }]}]}]}
    spans = parse_otlp_spans(payload)
    assert spans[0].raw_attributes["cached"] is True


def test_parser_multiple_resource_spans():
    """Parser handles multiple resourceSpans correctly."""
    payload = {"resourceSpans": [
        {"scopeSpans": [{"spans": [{"traceId": "t1", "spanId": "s1", "name": "a",
                                    "startTimeUnixNano": "0", "endTimeUnixNano": "0", "attributes": []}]}]},
        {"scopeSpans": [{"spans": [{"traceId": "t2", "spanId": "s2", "name": "b",
                                    "startTimeUnixNano": "0", "endTimeUnixNano": "0", "attributes": []}]}]},
    ]}
    spans = parse_otlp_spans(payload)
    assert len(spans) == 2
    assert spans[0].trace_id == "t1"
    assert spans[1].trace_id == "t2"


def test_parser_multiple_scope_spans():
    """Parser handles multiple scopeSpans within resourceSpan."""
    payload = {"resourceSpans": [{"scopeSpans": [
        {"spans": [{"traceId": "t", "spanId": "s1", "name": "a",
                   "startTimeUnixNano": "0", "endTimeUnixNano": "0", "attributes": []}]},
        {"spans": [{"traceId": "t", "spanId": "s2", "name": "b",
                   "startTimeUnixNano": "0", "endTimeUnixNano": "0", "attributes": []}]},
    ]}]}
    spans = parse_otlp_spans(payload)
    assert len(spans) == 2


def test_bridge_tool_with_no_safety_score_permits():
    """Tool spans without safety score default to permit."""
    span = _make_span("tool.read", safety_score=None)
    decision = process_span_action(span)
    assert decision.decision == "permit"


def test_bridge_evidence_id_uniqueness():
    """Each gated span gets unique evidence ID."""
    span1 = _make_span("tool.a", trace_id="same")
    span2 = _make_span("tool.b", trace_id="same")
    ev1 = process_span_action(span1).evidence_id
    ev2 = process_span_action(span2).evidence_id
    assert ev1 != ev2


def test_parser_tool_name_extraction_nested():
    """Action type extraction handles nested tool names."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "t", "spanId": "s", "name": "tool.file.write.async",
        "startTimeUnixNano": "0", "endTimeUnixNano": "0", "attributes": [],
    }]}]}]}
    spans = parse_otlp_spans(payload)
    assert spans[0].action_type == "file.write.async"


def test_parser_preserves_raw_attributes():
    """All attributes preserved in raw_attributes for extension."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "t", "spanId": "s", "name": "tool.test",
        "startTimeUnixNano": "0", "endTimeUnixNano": "0",
        "attributes": [
            {"key": "custom.field1", "value": {"stringValue": "val1"}},
            {"key": "custom.field2", "value": {"intValue": "42"}},
        ],
    }]}]}]}
    spans = parse_otlp_spans(payload)
    assert spans[0].raw_attributes["custom.field1"] == "val1"
    assert spans[0].raw_attributes["custom.field2"] == 42


def test_endpoint_latency_tracked(test_client):
    """Each result includes latency measurement."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "t", "spanId": "s", "name": "tool.test",
        "startTimeUnixNano": "0", "endTimeUnixNano": "0", "attributes": [],
    }]}]}]}
    data = test_client.post("/v1/traces", json=payload).json()
    assert data["results"][0]["latency_ms"] >= 0
    assert isinstance(data["results"][0]["latency_ms"], float)


# Defensive Edge Case Tests

def test_parser_attribute_without_key():
    """Parser handles attributes missing 'key' field gracefully."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "t", "spanId": "s", "name": "tool.test",
        "startTimeUnixNano": "0", "endTimeUnixNano": "0",
        "attributes": [
            {"value": {"stringValue": "orphan"}},  # Missing key
            {"key": "valid.key", "value": {"stringValue": "value"}},
        ],
    }]}]}]}
    spans = parse_otlp_spans(payload)
    assert len(spans) == 1
    assert "valid.key" in spans[0].raw_attributes
    assert len(spans[0].raw_attributes) == 1  # Orphan attribute skipped


def test_parser_name_exactly_tool_dot():
    """Parser handles edge case where name is exactly 'tool.' with no suffix."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "t", "spanId": "s", "name": "tool.",
        "startTimeUnixNano": "0", "endTimeUnixNano": "0", "attributes": [],
    }]}]}]}
    spans = parse_otlp_spans(payload)
    assert spans[0].name == "tool."
    assert spans[0].action_type is None  # Should be None, not empty string


def test_bridge_empty_trace_id():
    """Evidence ID handles empty trace_id gracefully."""
    span = _make_span("tool.test", trace_id="")
    decision = process_span_action(span)
    assert decision.evidence_id is not None
    assert decision.evidence_id.startswith("ev-notrace-")


def test_parser_span_missing_required_fields():
    """Parser handles spans missing traceId/spanId gracefully."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "name": "tool.test",
        "startTimeUnixNano": "0", "endTimeUnixNano": "0", "attributes": [],
    }]}]}]}
    spans = parse_otlp_spans(payload)
    assert len(spans) == 1
    assert spans[0].trace_id == ""
    assert spans[0].span_id == ""


def test_parser_empty_span_object():
    """Parser handles completely empty span object."""
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{}]}]}]}
    spans = parse_otlp_spans(payload)
    assert len(spans) == 1
    assert spans[0].name == ""
    assert spans[0].trace_id == ""


def test_bridge_gate_tier_values():
    """Gate tiers are correctly assigned based on decision."""
    permit_span = _make_span("tool.a", safety_score=800)
    deny_span = _make_span("tool.b", safety_score=100)
    pass_span = _make_span("llm.completion")

    assert process_span_action(permit_span).gate_tier == 0
    assert process_span_action(deny_span).gate_tier == 2
    assert process_span_action(pass_span).gate_tier is None
