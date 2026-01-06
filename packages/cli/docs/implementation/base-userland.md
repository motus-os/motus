# Base Userland Contract

This document describes the non-negotiable userland foundation that ships with Motus.
It is the minimum structure required for a safe, deterministic setup.

## Source of truth

- Standards contract: `packages/cli/docs/standards/userland-contract.md`
- Module registry: `packages/cli/docs/standards/module-registry.yaml`
- Release gate registry: `packages/cli/docs/standards/gates.yaml`

## Required layout

`motus init` creates the required `.motus/` structure. The paths below must exist.

- `.motus/current` (symlink)
- `.motus/releases/<version>/system/`
- `.motus/user/{skills,standards,config}/`
- `.motus/project/{skills,standards,config}/`
- `.motus/state/{ledger,evidence,orient,orient-cache,proposals,locks}/`

## Kernel databases

- `~/.motus/coordination.db` is the kernel source of truth.
- `~/.motus/context_cache.db` is derived and can be rebuilt.

## Registries

- **Modules**: `motus modules list` reads the module registry.
- **Release gates**: `motus gates list` reads the gate registry.
- **Policy gates**: `motus policy` loads gates from the vault.

## Gates

- Release gates are executable scripts under `scripts/gates/`.
- Policy gates run via `motus policy` and emit evidence bundles.
- Do not create new gate IDs without registering them.

## Evidence

Evidence bundles are append-only artifacts. Do not edit them in place.

## Quick validation

- `motus init`
- `motus doctor`
- `motus modules list`
- `motus gates list`

If any of these fail, the userland contract is not satisfied.
