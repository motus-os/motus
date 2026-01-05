# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Module entrypoint for `python -m motus.ui.web`."""

from motus.ui.web.app import run_web


def main() -> None:
    """Run the Motus Web UI."""
    run_web()


if __name__ == "__main__":
    main()
