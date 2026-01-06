# Userland Contract (Non-Negotiables)

Purpose: define the required local layout and registries for Motus userland.

## Scope

- Applies to workspace `.motus/` and global `~/.motus/` storage.
- Missing paths are a hard failure unless repaired via `motus init --force`.

## Storage Roots

| Root | Purpose | Source of Truth |
| --- | --- | --- |
| `~/.motus/` | Kernel state, databases, global config | CLI bootstrap + migrations |
| `<repo>/.motus/` | User/project standards, releases, local state | `motus init` |

## Required `.motus/` Layout

`motus init` creates the required structure. The paths below are non-negotiable.

| Path | Purpose | Notes |
| --- | --- | --- |
| `.motus/current` | Current release pointer | Must be a symlink |
| `.motus/releases/<version>/system/` | Packaged system release | Target of `current` |
| `.motus/user/skills/` | User skill packs | User-owned |
| `.motus/user/standards/` | User standards | User-owned |
| `.motus/user/config/` | User config overlays | User-owned |
| `.motus/project/skills/` | Project skill packs | Project-owned |
| `.motus/project/standards/` | Project standards | Project-owned |
| `.motus/project/config/` | Project config overlays | Project-owned |
| `.motus/state/ledger/` | Local ledger artifacts | Do not edit by hand |
| `.motus/state/evidence/` | Evidence bundles | Append-only |
| `.motus/state/orient/` | Orient events | Best-effort |
| `.motus/state/orient-cache/` | Orient cache | Safe to clear |
| `.motus/state/proposals/` | Standards proposals | Safe to clear after promotion |
| `.motus/state/locks/` | Claim registry locks | Safe to clear when idle |
| `.motus/scratch/` | Scratch entries + index | File-backed cache, rebuildable |

## Databases and Caches

- `~/.motus/coordination.db` is the kernel source of truth.
- `~/.motus/context_cache.db` is derived and can be rebuilt.
- `~/.motus/config.json` holds global defaults (never store API keys here).

## Registry Sources

- **Module registry**: `packages/cli/docs/standards/module-registry.yaml` (canonical).
- **Release gates**: `packages/cli/docs/standards/gates.yaml` (canonical).
- **Policy gates**: `<vault>/core/best-practices/gates.json` (loaded by `motus policy`).
- **Policy packs**: `<vault>/core/best-practices/skill-packs/registry.json`.
- **Policy profiles**: `<vault>/core/best-practices/profiles/profiles.json`.

Overrides:
- `MOTUS_MODULE_REGISTRY` for module registry path.
- `MOTUS_GATES_REGISTRY` for release gate registry path.

## Gates

- **Release gates** are `GATE-*` scripts in `scripts/gates/` and must be registered.
- **Policy gates** run via `motus policy` and emit evidence bundles.
- Do not invent new gate IDs without registering them.

## Evidence Bundles

- Policy evidence bundles live under `<repo>/.mc/evidence/<run_id>` by default.
- Override via `MC_EVIDENCE_DIR` or `evidence_dir` in config.
- Evidence bundles are append-only; do not edit artifacts in place.
