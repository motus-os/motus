"""Compatibility shim for claim registry exports."""

from .claims_core import ClaimConflict, ClaimRegistry
from .claims_validation import ClaimRegistryError

__all__ = ["ClaimConflict", "ClaimRegistry", "ClaimRegistryError"]
