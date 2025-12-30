"""Compatibility shim for harness exports."""

from .harness_core import MCTestHarness, TestHarness, detect_harness

__all__ = ["MCTestHarness", "TestHarness", "detect_harness"]
