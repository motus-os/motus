from __future__ import annotations

import json
from pathlib import Path

import pytest

from motus.motus_fs import create_motus_tree
from motus.standards.proposals import PromotionError, ProposalManager, context_hash


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _setup_vault_schema(tmp_path: Path, monkeypatch) -> None:
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("MC_VAULT_DIR", str(vault_dir))

    _write_json(
        vault_dir / "core/best-practices/control-plane/standard.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": True,
            "required": ["id", "type", "version", "applies_if", "output"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "type": {"type": "string", "minLength": 1},
                "version": {"type": "string", "minLength": 1},
                "applies_if": {"type": "object"},
                "output": {"type": "object"},
                "layer": {"type": "string", "enum": ["system", "project", "user"]},
                "status": {"type": "string", "enum": ["active", "deprecated"]},
                "priority": {"type": "integer"},
                "rationale": {"type": "string"},
            },
        },
    )


def test_propose_list_reject_and_promote(tmp_path: Path, monkeypatch):
    _setup_vault_schema(tmp_path, monkeypatch)

    motus_dir = tmp_path / ".motus"
    motus_dir.mkdir()
    create_motus_tree(motus_dir)

    now_values = iter(
        [
            "2025-12-18T00:00:00Z",
            "2025-12-18T00:00:01Z",
            "2025-12-18T00:00:02Z",
            "2025-12-18T00:00:03Z",
        ]
    )

    def now() -> str:
        return next(now_values)

    manager = ProposalManager(motus_dir=motus_dir, now=now)

    ctx = {"artifact": "chart", "theme": "dark"}
    out = {"palette": "dark-mode-12"}

    proposal, proposal_path = manager.propose(
        decision_type="color_palette",
        context=ctx,
        output=out,
        proposed_by="agent-1",
        why="Dark mode needed",
    )

    assert proposal.status == "pending"
    assert proposal.context_hash == context_hash(ctx)
    assert proposal_path.exists()

    listed = manager.list_proposals(status="pending")
    assert [p.proposal_id for p, _ in listed] == [proposal.proposal_id]

    rejected, rejected_path = manager.reject(proposal.proposal_id, reason="Not needed")
    assert rejected.status == "rejected"
    assert rejected.rejected_reason == "Not needed"
    assert not proposal_path.exists()
    assert rejected_path.exists()

    # Re-propose and promote.
    proposal2, _ = manager.propose(
        decision_type="color_palette",
        context=ctx,
        output=out,
        proposed_by="agent-1",
        why="Dark mode needed",
    )

    with pytest.raises(PromotionError):
        manager.promote(proposal2.proposal_id, to_layer="system")

    standard, standard_path, updated, updated_path = manager.promote(
        proposal2.proposal_id, to_layer="user"
    )
    assert standard_path.exists()
    assert updated.status == "approved"
    assert updated.promoted_layer == "user"
    assert updated_path.exists()
