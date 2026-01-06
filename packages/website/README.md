# Motus Website

Public documentation and product site for Motus. The canonical source lives in
`packages/website/` inside the public monorepo.

## Scope and ownership

- Public website source lives here: `packages/website/`.
- Internal planning and handoffs stay in private/internal repos and are not
  published through this site.
- Do not edit generated data by hand:
  - `packages/website/src/data/module-registry.json`
  - `packages/website/src/data/persona-map.json`
  - `packages/website/src/data/proof-ledger.json`
- The module registry source of truth is
  `packages/cli/docs/standards/module-registry.yaml`.
- `vision.json` will be added when the vision pipeline lands.
- The persona map source of truth is
  `packages/cli/docs/website/persona-map.yaml`.
- The site proof ledger source of truth is
  `packages/cli/docs/website/proof-ledger.yaml` (legacy, read-only).
- The marketing claims registry is `packages/website/standards/proof-ledger.json`
  and is enforced by the content standard.

## Review Process

Website changes follow a structured review process. See:

- `REVIEW-PROCESS.md` - Full 8-phase review with gates and validation modes
- `CONTENT-STANDARD.md` - Short pre-writing checklist (hard gates)
- `CLAUDE.md` - Voice, design system, copy guidelines
- `standards/proof-ledger.json` - Claims registry
- `standards/terminology.json` - Approved/banned terms
- `standards/tailwind-arbitrary-allowlist.txt` - Allowed Tailwind arbitrary values

## Local development

```bash
npm install
npm run dev -- --host 127.0.0.1 --port 4321
```

Open `http://localhost:4321/`.

## Production build (GitHub Pages)

```bash
ASTRO_SITE=https://motus-os.github.io ASTRO_BASE=/motus npm run build
```

Preview the build:

```bash
ASTRO_SITE=https://motus-os.github.io ASTRO_BASE=/motus npm run preview -- --host 127.0.0.1 --port 4321
```

## Deployment

GitHub Pages deploys via `.github/workflows/deploy-website.yml`. The workflow
builds the site and publishes to the repo Pages environment. If you want manual
approval before deploys, enable required reviewers on the `github-pages`
environment in GitHub settings.
