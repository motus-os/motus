# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ..commands.utils import redact_secrets
from .extractor import ErrorSummary


def print_error_summary(summary: ErrorSummary) -> None:
    console = Console()

    console.print()
    console.print(f"[bold]Errors:[/bold] {summary.total_errors}")

    if summary.total_errors == 0:
        return

    if summary.by_category:
        table = Table(title="By Category")
        table.add_column("Category")
        table.add_column("Count", justify="right")
        table.add_column("Percent", justify="right")
        for category, count in summary.by_category.items():
            pct = (count / summary.total_errors) * 100 if summary.total_errors else 0.0
            table.add_row(category, str(count), f"{pct:.0f}%")
        console.print(table)

    if summary.by_http_status:
        table = Table(title="API Errors (HTTP Status)")
        table.add_column("Status", justify="right")
        table.add_column("Count", justify="right")
        for status, count in sorted(summary.by_http_status.items()):
            table.add_row(str(status), str(count))
        console.print(table)

    if summary.by_exit_code:
        table = Table(title="Exit Codes")
        table.add_column("Exit Code", justify="right")
        table.add_column("Count", justify="right")
        for code, count in sorted(summary.by_exit_code.items()):
            table.add_row(str(code), str(count))
        console.print(table)

    if summary.by_file_error:
        table = Table(title="File I/O Errors")
        table.add_column("Kind")
        table.add_column("Count", justify="right")
        for kind, count in sorted(summary.by_file_error.items()):
            table.add_row(kind, str(count))
        console.print(table)

    if summary.first_errors:
        console.print()
        console.print("[bold]First Errors (chronological)[/bold]")
        for item in summary.first_errors:
            console.print(redact_secrets(item.message))


def summary_to_json(summary: ErrorSummary) -> str:
    import json

    return json.dumps(summary.to_dict(), indent=2, sort_keys=True)
