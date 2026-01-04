# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Intent YAML persistence helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# PyYAML lacks type stubs in our environment.
import yaml  # type: ignore[import-untyped]

from .file_lock import FileLockError, file_lock
from .intent_models import Intent
from .logging import get_logger

logger = get_logger(__name__)


def generate_intent_yaml(intent: Intent) -> str:
    data = intent.to_dict()
    return yaml.safe_dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True, width=80
    )


def load_intent(mc_dir: Path) -> Optional[Intent]:
    intent_file = mc_dir / "intent.yaml"

    if not intent_file.exists():
        logger.debug("Intent file not found", intent_file=str(intent_file))
        return None

    try:
        with file_lock(intent_file, exclusive=False):
            with open(intent_file, "r") as f:
                data = yaml.safe_load(f)

        if not data:
            logger.warning("Empty intent file", intent_file=str(intent_file))
            return None

        return Intent.from_dict(data)

    except FileLockError as e:
        logger.warning(
            "Failed to acquire intent lock",
            intent_file=str(intent_file),
            error_type=type(e).__name__,
            error=str(e),
        )
        return None
    except yaml.YAMLError as e:
        logger.error(
            "Failed to parse intent YAML",
            error_type=type(e).__name__,
            error=str(e),
        )
        return None
    except OSError as e:
        logger.error(
            "Failed to read intent file",
            error_type=type(e).__name__,
            error=str(e),
        )
        return None


def save_intent(mc_dir: Path, intent: Intent) -> bool:
    try:
        mc_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(
            "Failed to create .mc directory",
            error_type=type(e).__name__,
            error=str(e),
        )
        return False

    intent_file = mc_dir / "intent.yaml"

    try:
        yaml_str = generate_intent_yaml(intent)
        with file_lock(intent_file, exclusive=True):
            with open(intent_file, "w") as f:
                f.write(yaml_str)

        logger.info("Saved intent to file", intent_file=str(intent_file))
        return True

    except FileLockError as e:
        logger.error(
            "Failed to acquire intent lock",
            intent_file=str(intent_file),
            error_type=type(e).__name__,
            error=str(e),
        )
        return False
    except OSError as e:
        logger.error(
            "Failed to write intent file",
            error_type=type(e).__name__,
            error=str(e),
        )
        return False
