# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Proposal capture + promotion pipeline for standards."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Literal

import yaml  # type: ignore[import-untyped]

from motus.atomic_io import atomic_write_text
from motus.orient.index import StandardsIndex
from motus.standards.schema import Standard
from motus.standards.schemas import Proposal, ProposalStatus
from motus.standards.validator import StandardsValidator

from .proposals_helpers import (
    PromotionError,
    ProposalError,
    _proposal_filename,
    _require_dict,
    _require_mapping,
    _require_str,
    _slugify,
    _status_dir,
    _utc_now_iso_z,
    context_hash,
)

PromoteTarget = Literal["user", "project", "system"]
PromoteLayer = Literal["user", "project"]

PROPOSAL_SCHEMA_ID = "motus.standards.proposal.v1"


class ProposalManager:
    def __init__(
        self,
        *,
        motus_dir: Path,
        now: Callable[[], str] | None = None,
        validator: StandardsValidator | None = None,
    ) -> None:
        self._motus_dir = motus_dir
        self._root = motus_dir / "state" / "proposals"
        self._now = now or _utc_now_iso_z
        self._validator = validator or StandardsValidator()

    @property
    def root(self) -> Path:
        return self._root

    def ensure_dirs(self) -> None:
        for status in ("pending", "approved", "rejected"):
            _status_dir(self._root, status).mkdir(parents=True, exist_ok=True)

    def propose(
        self,
        *,
        decision_type: str,
        context: dict[str, Any],
        output: dict[str, Any],
        proposed_by: str,
        why: str | None = None,
    ) -> tuple[Proposal, Path]:
        self.ensure_dirs()

        created_at = self._now()
        ctx_hash = context_hash(context)
        # File-safe timestamp prefix for uniqueness (avoid collisions for repeated contexts).
        ts = created_at.replace("-", "").replace(":", "").replace("T", "").replace("Z", "")
        proposal_id = f"prop-{ts}-{_slugify(decision_type)}-{ctx_hash[:8]}"

        proposal = Proposal(
            schema=PROPOSAL_SCHEMA_ID,
            proposal_id=proposal_id,
            decision_type=decision_type,
            context_hash=ctx_hash,
            context_sample=context,
            proposed_output=output,
            proposed_by=proposed_by,
            created_at=created_at,
            status="pending",
            why=why,
            outcome_signals=[],
        )

        path = _status_dir(self._root, "pending") / _proposal_filename(proposal_id)
        if path.exists():
            raise ProposalError(f"Proposal already exists: {proposal_id}")

        content = yaml.safe_dump(proposal.to_dict(), sort_keys=True)
        atomic_write_text(path, content)
        return proposal, path

    def list_proposals(
        self,
        *,
        decision_type: str | None = None,
        status: ProposalStatus | None = None,
    ) -> list[tuple[Proposal, Path]]:
        self.ensure_dirs()

        statuses: tuple[ProposalStatus, ...] = (
            (status,) if status is not None else ("pending", "approved", "rejected")
        )

        out: list[tuple[Proposal, Path]] = []
        for st in statuses:
            base = _status_dir(self._root, st)
            for path in sorted(base.glob("*.yaml")):
                proposal = self._load_path(path)
                if decision_type is not None and proposal.decision_type != decision_type:
                    continue
                out.append((proposal, path))

        out.sort(key=lambda x: (x[0].created_at, x[0].proposal_id))
        return out

    def load(self, proposal_id: str) -> tuple[Proposal, Path]:
        self.ensure_dirs()

        hits: list[Path] = []
        for st in ("pending", "approved", "rejected"):
            p = _status_dir(self._root, st) / _proposal_filename(proposal_id)
            if p.exists():
                hits.append(p)

        if not hits:
            raise ProposalError(f"Proposal not found: {proposal_id}")
        if len(hits) > 1:
            raise ProposalError(f"Proposal exists in multiple status dirs: {proposal_id}")

        path = hits[0]
        return self._load_path(path), path

    def reject(self, proposal_id: str, *, reason: str) -> tuple[Proposal, Path]:
        proposal, path = self.load(proposal_id)
        if proposal.status != "pending":
            raise ProposalError(f"Cannot reject non-pending proposal: {proposal_id}")

        updated = replace(
            proposal,
            status="rejected",
            rejected_reason=reason,
            rejected_at=self._now(),
        )

        dest = _status_dir(self._root, "rejected") / _proposal_filename(proposal_id)
        content = yaml.safe_dump(updated.to_dict(), sort_keys=True)
        atomic_write_text(dest, content)
        path.unlink(missing_ok=True)
        return updated, dest

    def promote(
        self, proposal_id: str, *, to_layer: PromoteTarget
    ) -> tuple[Standard, Path, Proposal, Path]:
        if to_layer == "system":
            raise PromotionError("System layer is immutable; promote to user/project")

        layer: PromoteLayer = to_layer

        proposal, proposal_path = self.load(proposal_id)
        if proposal.status != "pending":
            raise ProposalError(f"Cannot promote non-pending proposal: {proposal_id}")

        standard_id = proposal_id.replace("prop-", "proposal.")
        standard = Standard(
            id=standard_id,
            type=proposal.decision_type,
            version="1.0.0",
            applies_if=dict(proposal.context_sample),
            output=dict(proposal.proposed_output),
            layer=layer,
            status="active",
            priority=0,
            rationale=proposal.why,
        )

        standard_dir = self._motus_dir / layer / "standards" / proposal.decision_type / standard.id
        standard_path = standard_dir / "standard.yaml"
        if standard_path.exists():
            raise PromotionError(f"Standard already exists: {standard_path}")

        # Validate before activation (fail-closed).
        standard_dir.mkdir(parents=True, exist_ok=True)
        standard_yaml = yaml.safe_dump(
            {
                "id": standard.id,
                "type": standard.type,
                "version": standard.version,
                "applies_if": standard.applies_if,
                "output": standard.output,
                "layer": standard.layer,
                "status": standard.status,
                "priority": standard.priority,
                "rationale": standard.rationale,
            },
            sort_keys=True,
        )
        atomic_write_text(standard_path, standard_yaml)

        validation = self._validator.validate(standard_path)
        if not validation.ok:
            standard_path.unlink(missing_ok=True)
            raise PromotionError("Standard validation failed: " + "; ".join(validation.errors))

        updated_proposal = replace(
            proposal,
            status="approved",
            promoted_to=standard.id,
            promoted_layer=layer,
            promoted_at=self._now(),
        )

        dest = _status_dir(self._root, "approved") / _proposal_filename(proposal_id)
        content = yaml.safe_dump(updated_proposal.to_dict(), sort_keys=True)
        atomic_write_text(dest, content)
        proposal_path.unlink(missing_ok=True)

        # Explicit rebuild of standards index (keeps `motus orient` deterministic + fresh).
        StandardsIndex.load_or_build(self._motus_dir, rebuild=True)

        return standard, standard_path, updated_proposal, dest

    def _load_path(self, path: Path) -> Proposal:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        m = _require_mapping(raw, path=path)

        schema = _require_str(m.get("schema"), field="schema", path=path)
        proposal_id = _require_str(m.get("proposal_id"), field="proposal_id", path=path)
        decision_type = _require_str(m.get("decision_type"), field="decision_type", path=path)
        ctx_hash = _require_str(m.get("context_hash"), field="context_hash", path=path)
        ctx_sample = _require_dict(m.get("context_sample") or {}, field="context_sample", path=path)
        proposed_output = _require_dict(m.get("proposed_output") or {}, field="proposed_output", path=path)
        proposed_by = _require_str(m.get("proposed_by"), field="proposed_by", path=path)
        created_at = _require_str(m.get("created_at"), field="created_at", path=path)

        status_raw = m.get("status") or "pending"
        if status_raw not in ("pending", "approved", "rejected"):
            raise ProposalError(f"Invalid proposal status: {status_raw}")
        status: ProposalStatus = status_raw

        why = m.get("why")
        if why is not None and not isinstance(why, str):
            raise ProposalError(f"Invalid proposal why (must be string): {path}")

        signals_raw = m.get("outcome_signals") or []
        if not isinstance(signals_raw, list) or not all(isinstance(s, str) for s in signals_raw):
            raise ProposalError(f"Invalid proposal outcome_signals (must be list[str]): {path}")

        promoted_to = m.get("promoted_to")
        if promoted_to is not None and not isinstance(promoted_to, str):
            raise ProposalError(f"Invalid proposal promoted_to (must be string): {path}")

        promoted_layer = m.get("promoted_layer")
        if promoted_layer is not None and promoted_layer not in ("user", "project"):
            raise ProposalError(f"Invalid proposal promoted_layer (must be user|project): {path}")

        promoted_at = m.get("promoted_at")
        if promoted_at is not None and not isinstance(promoted_at, str):
            raise ProposalError(f"Invalid proposal promoted_at (must be string): {path}")

        rejected_reason = m.get("rejected_reason")
        if rejected_reason is not None and not isinstance(rejected_reason, str):
            raise ProposalError(f"Invalid proposal rejected_reason (must be string): {path}")

        rejected_at = m.get("rejected_at")
        if rejected_at is not None and not isinstance(rejected_at, str):
            raise ProposalError(f"Invalid proposal rejected_at (must be string): {path}")

        return Proposal(
            schema=schema,
            proposal_id=proposal_id,
            decision_type=decision_type,
            context_hash=ctx_hash,
            context_sample=ctx_sample,
            proposed_output=proposed_output,
            proposed_by=proposed_by,
            created_at=created_at,
            status=status,
            why=why,
            outcome_signals=list(signals_raw),
            promoted_to=promoted_to,
            promoted_layer=promoted_layer,  # type: ignore[arg-type]
            promoted_at=promoted_at,
            rejected_reason=rejected_reason,
            rejected_at=rejected_at,
        )
