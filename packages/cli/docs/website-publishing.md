# Website Publishing and Repo Boundaries

This document defines the canonical source of truth for the public website and
the deployment flow that keeps the website and codebase aligned.

## Canonical source of truth

- Public website code lives in `packages/website/` in the public monorepo.
- Internal planning docs, handoffs, and experiments stay in private/internal
  repos and must not be published.
- The public site consumes generated data files:
  - `packages/website/src/data/module-registry.json`
  - `packages/website/src/data/vision.json` (when the vision pipeline lands)
  - `packages/website/src/data/persona-map.json`
  - `packages/website/src/data/proof-ledger.json`

## Registry gate

The module registry is authored in
`packages/cli/docs/standards/module-registry.yaml`. The site uses the JSON
version. CI enforces that YAML and JSON stay in sync before deploy.

The proof ledger is authored in `packages/cli/docs/website/proof-ledger.yaml`
and synced to `packages/website/src/data/proof-ledger.json`. CI enforces the
sync so claims cannot ship without proof references.

The persona map is authored in `packages/cli/docs/website/persona-map.yaml` and
synced to `packages/website/src/data/persona-map.json`. This is an editorial
artifact and is not gated in CI.

The UI rhythm checklist lives in `packages/cli/docs/website/ui-checklist.md`
and defines the layout/typography guardrails for new sections.

## Deployment flow

1. Changes merge into `main`.
2. `deploy-website.yml` builds the site with:
   - `ASTRO_SITE=https://motus-os.github.io`
   - `ASTRO_BASE=/motus`
3. GitHub Pages publishes the build artifact.

If you want a manual approval step, configure required reviewers on the
`github-pages` environment in GitHub settings.

## Local development

```bash
cd packages/website
npm install
npm run dev -- --host 127.0.0.1 --port 4321
```

Open `http://localhost:4321/`.
