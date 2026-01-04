# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""OTLP trace ingest endpoint for universal agent governance."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from motus.ingest.bridge import process_span_action
from motus.ingest.parser import parse_otlp_spans


@dataclass
class IngestResult:
    """Result of processing a single span."""

    trace_id: str
    span_id: str
    decision: str  # "permit" | "deny" | "pass"
    reason: str | None
    evidence_id: str | None
    latency_ms: float


@dataclass
class IngestResponse:
    """Response from trace ingest endpoint."""

    received: int
    processed: int
    results: list[IngestResult] = field(default_factory=list)


class OTLPIngestApp:
    """OTLP trace ingest application."""

    def __init__(self) -> None:
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        app = FastAPI(title="Motus OTLP Ingest")

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "healthy"}

        @app.post("/v1/traces")
        async def ingest_traces(request: Request) -> JSONResponse:
            try:
                body: dict[str, Any] = await request.json()
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Invalid JSON body")

            try:
                spans = parse_otlp_spans(body)
            except (KeyError, ValueError, TypeError) as e:
                raise HTTPException(status_code=422, detail=f"Failed to parse OTLP: {e}")

            results: list[IngestResult] = []
            for span in spans:
                start = time.perf_counter()
                try:
                    action_result = process_span_action(span)
                    latency = (time.perf_counter() - start) * 1000
                    results.append(IngestResult(
                        trace_id=span.trace_id,
                        span_id=span.span_id,
                        decision=action_result.decision,
                        reason=action_result.reason,
                        evidence_id=action_result.evidence_id,
                        latency_ms=round(latency, 3),
                    ))
                except (KeyError, ValueError, TypeError, RuntimeError):
                    latency = (time.perf_counter() - start) * 1000
                    results.append(IngestResult(
                        trace_id=span.trace_id,
                        span_id=span.span_id,
                        decision="pass",
                        reason="Processing error",
                        evidence_id=None,
                        latency_ms=round(latency, 3),
                    ))

            response = IngestResponse(received=len(spans), processed=len(results), results=results)
            return JSONResponse(content={
                "received": response.received,
                "processed": response.processed,
                "results": [vars(r) for r in response.results],
            })

        return app


def create_app() -> FastAPI:
    """Factory function to create the OTLP ingest app."""
    return OTLPIngestApp().app
