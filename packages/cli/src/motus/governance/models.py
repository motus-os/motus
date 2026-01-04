# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _generate_uuid() -> str:
    return str(uuid4())


class ActorType(str, Enum):
    HUMAN = "human"
    AGENT = "agent"
    AUTOMATION = "automation"


class Actor(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    type: ActorType
    name: str
    model: Optional[str] = None


class FileHash(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    path: str
    sha256: str


class ToolInfo(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    name: str
    version: Optional[str] = None


class CheckResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    check_id: str
    result: str  # pass|fail


class WorkReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    receipt_version: str = "0.1.0"
    timestamp_utc: datetime = Field(default_factory=datetime.utcnow)
    work_id: str = Field(default_factory=_generate_uuid)
    actor: Actor
    inputs: List[FileHash] = Field(default_factory=list)
    outputs: List[FileHash] = Field(default_factory=list)
    tools_used: List[ToolInfo] = Field(default_factory=list)
    checks: List[CheckResult] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    bundle_id: str = Field(default_factory=_generate_uuid)
    manifest_version: str = "0.1.0"
    timestamp_utc: datetime = Field(default_factory=datetime.utcnow)
    hashes: List[FileHash]
    scope: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)


class ChangeType(str, Enum):
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"


class ContributionEvent(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    event_id: str = Field(default_factory=_generate_uuid)
    timestamp_utc: datetime = Field(default_factory=datetime.utcnow)
    actor: Actor
    artifact_id: str
    change_type: ChangeType
    hash_before: Optional[str] = None
    hash_after: Optional[str] = None
    evidence_bundle_id: Optional[str] = None
    notes: Optional[str] = None
