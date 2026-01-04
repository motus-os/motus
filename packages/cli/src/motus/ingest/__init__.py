# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""OTLP telemetry ingest for universal agent governance."""

from motus.ingest.bridge import process_span_action
from motus.ingest.otlp import OTLPIngestApp, create_app
from motus.ingest.parser import SpanAction, parse_otlp_spans

__all__ = [
    "OTLPIngestApp",
    "create_app",
    "parse_otlp_spans",
    "SpanAction",
    "process_span_action",
]
