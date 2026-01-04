# Motus (Public) - Agent Instructions

## Canonical Repo

- **Canonical path:** `/Users/ben/GitHub/motus`
- **Remote:** `motus-os/motus`
- **Public work happens here.**

## Internal Repo (Do Not Use for Public Changes)

- `/Users/ben/GitHub/motus-command` is internal-only.
- Any public-facing changes must be ported into the canonical repo.

## Repo Layout

- CLI: `packages/cli/`
- Website: `packages/website/`

If you need internal handoffs or `.ai/` artifacts, use the internal repo.

## Governance Files (Root Canonical)

**All governance files live at repo root. No duplication.**

| File | Location | Scope |
|------|----------|-------|
| `SECURITY.md` | Root | Repo-wide vulnerability policy |
| `CONTRIBUTING.md` | Root | Repo-wide contribution guide |
| `CODE_OF_CONDUCT.md` | Root | Repo-wide community standards |
| `ARCHITECTURE.md` | Root | High-level system design |
| `CHANGELOG.md` | Root | Repo-wide version history |
| `README.md` | Root | Project overview, value prop, quickstart |

**Package-level READMEs** (`packages/cli/README.md`, `packages/website/README.md`) cover package-specific usage only.

**Why:** Single source of truth. Zero sync burden. CTOs find files where expected. GitHub surfaces them properly.
