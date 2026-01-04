# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Allow running the CLI as python -m motus.cli"""

from .core import main

if __name__ == "__main__":
    main()
