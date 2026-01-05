# Handoff: Tutorial Framework + Ecosystem Redesign

**Date**: 2026-01-05
**From**: Content/Marketing Agent
**To**: Website Implementation Agent
**Status**: Workstream B (Tutorial) IMPLEMENTED - GIF/Demo tasks remain
**Verified**: All commands validated against motusos 0.5.2

---

## Implementation Status

| Item | Status | Notes |
|------|--------|-------|
| `tutorial.yaml` | DONE | Source of truth created |
| `validate-tutorial.py` | DONE | CI validation script |
| `validate-tutorial.yml` | DONE | GitHub workflow |
| VHS scripts (6 files) | DONE | Ready to run |
| `get-started.astro` | DONE | Page rewritten, consumes YAML |
| GIF assets | PENDING | Need to run VHS scripts |
| Demo repo script | PENDING | Need to create |
| Demo repo template | PENDING | Need to create |

---

## Overview

Two complementary workstreams are ready for implementation. They share the same status system and truth-first principles but touch different files.

### Workstream A: Ecosystem Map Redesign
**Priority**: Execute first
**Goal**: Transform the ecosystem map from a parts list into a directed story

### Workstream B: Tutorial Framework
**Priority**: Execute second
**Goal**: Replace command reference with "Build with Receipts" guided tutorial

---

## Workstream A: Ecosystem Map Redesign

### Already Approved Plan

Execute the following batches in order:

#### Batch A-1: Data + Guardrails (truth enforcement first)

1. Update `packages/cli/docs/website/ecosystem-map.yaml` to support:
   - `lane` positioning (`position`, `arrow_to`)
   - `visibility` (`prominent`/`visible`/`teaser`/`hidden`)
   - `motus_adds` (value statement for external nodes)

2. Extend `packages/cli/scripts/ci/check_ecosystem_map.py` to enforce:
   - Lanes + positions present
   - External nodes require `motus_adds`
   - Future nodes cannot be `prominent`

3. Regenerate `packages/website/src/data/ecosystem-map.json` and keep YAML/JSON in sync

#### Batch A-2: UI Flow (story before structure)

1. Replace the 3x3 grid with horizontal flow diagram above the fold:
   ```
   [Inputs] → [Core] → [Governance] → [Economy]
                ↓
            [Modules]
   ```

2. Status rendered visually:
   - Current: solid lines, 100% opacity
   - Building: dashed lines, 70% opacity
   - Future: dotted lines, 40% opacity

3. Below the fold: progressive disclosure
   - Lane toggles
   - Expandable item detail panel

4. Mobile: accordion lanes with clear hierarchy (not scroll dump)

#### Batch A-3: Defaults + Polish

- Show Current only on first load; toggle reveals Building/Future
- Every external logo shows "Motus adds" as the headline
- Clickable wayfinding: click lane → scroll to detail

### Success Criteria

- 5-second test: "I know where Motus fits"
- Status clarity: current vs future is obvious without reading badges
- Value clarity: every external logo answers "so what"

### Files Touched (Ecosystem)

```
packages/cli/docs/website/ecosystem-map.yaml       # Add lane/visibility fields
packages/cli/scripts/ci/check_ecosystem_map.py     # Add new validations
packages/website/src/data/ecosystem-map.json       # Regenerated from YAML
packages/website/src/pages/docs/ecosystem.astro    # New layout
packages/website/src/components/EcosystemFlow.astro      # Replace with horizontal flow
packages/website/src/components/EcosystemFlowMobile.astro # Replace with accordion
```

---

## Workstream B: Tutorial Framework

### New Files Created (Ready for Use)

| File | Purpose |
|------|---------|
| `packages/website/src/data/tutorial.yaml` | Source of truth for all tutorial steps |
| `scripts/validate-tutorial.py` | CI script that executes every step |
| `.github/workflows/validate-tutorial.yml` | CI workflow for validation + GIF generation |
| `packages/website/vhs-scripts/tutorial-*.tape` | VHS scripts for deterministic GIFs |

### What tutorial.yaml Contains

```yaml
meta:
  title: "Build a Python app with receipts"
  duration_minutes: 30

prerequisites:
  - python 3.10+
  - pip

setup:
  - pip install motusos
  - motus init --lite
  - motus doctor

features:
  - DEMO-001: Add greeting function (current)
  - DEMO-002: Add input validation (current)
  - DEMO-003: Add CLI entry point (current)

reveal:
  - motus work list (shows all 3 completed tasks)

demo_repo:
  - Generated from tutorial execution
  - Includes .motus/ database with all receipts
```

### Page Implementation Required

The existing `get-started.astro` should be replaced with a new structure:

```
[Hero]
  "Build something. Prove you built it."
  "Create a Python app with complete audit trail in 30 minutes."

[Setup] (collapsed by default)
  - Install
  - Init
  - Doctor

[The Build] (3 expandable features)
  Each feature shows:
  - Claim command + GIF
  - Code to write
  - Evidence command + GIF
  - Release command + GIF
  - Receipt view + GIF

[The Reveal]
  - motus work list showing all 3 tasks
  - "This is what accountability looks like"

[Download]
  - Link to demo repo ZIP
  - Link to GitHub repo

[Next Steps]
  - Links to how-it-works, implementation, demos
```

### Status Controls

Tutorial steps use the same status system as the rest of the site:

```javascript
// Use existing lib/status.js
import { getStatusClass, getStatusLabel } from '../lib/status.js';

// Only show current steps as interactive
// Building steps show with "Coming Soon" badge
// Future steps are hidden
```

### GIF Assets

VHS scripts are in `packages/website/vhs-scripts/`:
- `tutorial-01-claim.tape` → `01-claim.gif`
- `tutorial-02-evidence.tape` → `02-evidence.gif`
- `tutorial-03-release.tape` → `03-release.gif`
- `tutorial-04-receipt.tape` → `04-receipt.gif`
- `tutorial-05-reveal-1.tape` → `05-reveal-1.gif` (first receipt)
- `tutorial-05-reveal-3.tape` → `05-reveal-3.gif` (all 3 receipts)

GIFs output to `packages/website/public/assets/tutorial/`

### Command Verification (2026-01-05)

All tutorial commands verified against `motusos 0.1.0`:

| Command | Status | Notes |
|---------|--------|-------|
| `motus work claim` | VERIFIED | Returns lease_id |
| `motus work context` | VERIFIED | Gets Lens context |
| `motus work outcome` | VERIFIED | Registers deliverables |
| `motus work evidence` | VERIFIED | Records test results |
| `motus work decision` | VERIFIED | Logs decisions |
| `motus work release` | VERIFIED | Releases with outcome |
| `motus work status` | VERIFIED | Shows full receipt |
| `motus work list` | NOT AVAILABLE | Does not exist - use individual status |
| `motus work export` | NOT AVAILABLE | Does not exist - removed from tutorial |

The reveal section uses `motus work status` for each lease instead of a list command.

---

## REMAINING TASKS: GIF Generation

### Prerequisites

1. Install VHS (terminal recorder):
   ```bash
   brew install charmbracelet/tap/vhs
   ```

2. Install ttyd (web terminal, required by VHS):
   ```bash
   brew install ttyd
   ```

3. Ensure motusos is installed:
   ```bash
   pip install motusos
   motus --version  # Should show 0.5.x
   ```

### Generate GIFs

Run each VHS script from the website package root:

```bash
cd packages/website

# Generate all tutorial GIFs
vhs vhs-scripts/tutorial-01-claim.tape
vhs vhs-scripts/tutorial-02-evidence.tape
vhs vhs-scripts/tutorial-03-release.tape
vhs vhs-scripts/tutorial-04-receipt.tape
vhs vhs-scripts/tutorial-05-reveal-1.tape
vhs vhs-scripts/tutorial-05-reveal-3.tape
```

GIFs will be output to `public/assets/tutorial/`:
- `01-claim.gif` (600x400)
- `02-evidence.gif` (600x400)
- `03-release.gif` (600x400)
- `04-receipt.gif` (900x500)
- `05-reveal-1.gif` (900x500)
- `05-reveal-3.gif` (900x600)

### Verify GIFs

```bash
# Check all GIFs were generated
ls -la public/assets/tutorial/*.gif

# Verify sizes (should be under 2MB each)
du -h public/assets/tutorial/*.gif
```

### Update get-started.astro to Display GIFs

The page already has placeholder logic. When GIFs exist, they should be displayed inline with steps that have `gif: true` in tutorial.yaml.

Look for this pattern in each step:
```astro
{step.gif && (
  <img src={getGifPath(step.gif_name)} alt={step.title} class="rounded-lg" />
)}
```

---

## REMAINING TASKS: Demo Repository

### Create Demo Repo Generator Script

Create `scripts/generate-demo-repo.py`:

```python
#!/usr/bin/env python3
"""Generate the motus-demo-app repository from tutorial.yaml."""

import yaml
import subprocess
import shutil
from pathlib import Path
from jinja2 import Template

def main():
    # 1. Load tutorial.yaml
    with open('packages/website/src/data/tutorial.yaml') as f:
        tutorial = yaml.safe_load(f)

    # 2. Create temp directory
    demo_dir = Path('/tmp/motus-demo-app')
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    demo_dir.mkdir()

    # 3. Initialize Motus
    subprocess.run(['motus', 'init', '--lite', '--path', str(demo_dir)], check=True)

    # 4. Execute each feature
    for feature in tutorial['features']:
        lease_id = None
        for step in feature['steps']:
            if step['type'] == 'file':
                # Write file
                (demo_dir / step['path']).write_text(step['content'])
            elif step['type'] == 'command':
                # Execute command
                cmd = step['command']
                if '${lease_id}' in cmd and lease_id:
                    cmd = cmd.replace('${lease_id}', lease_id)

                result = subprocess.run(
                    cmd, shell=True, cwd=demo_dir,
                    capture_output=True, text=True
                )

                # Capture lease_id if needed
                if step.get('capture_output'):
                    import re
                    pattern = step['capture_output']['pattern']
                    match = re.search(pattern, result.stdout)
                    if match:
                        lease_id = match.group(0)

    # 5. Generate README from template
    with open('packages/website/templates/demo-repo-readme.md.jinja') as f:
        template = Template(f.read())

    readme = template.render(
        title=tutorial['demo_repo']['name'],
        description=tutorial['demo_repo']['description'],
        features=tutorial['features']
    )
    (demo_dir / 'README.md').write_text(readme)

    # 6. Write static files
    for static in tutorial['demo_repo']['static_files']:
        if 'content' in static:
            (demo_dir / static['path']).write_text(static['content'])

    print(f"Demo repo generated at: {demo_dir}")
    print("Files:")
    for f in demo_dir.rglob('*'):
        if f.is_file():
            print(f"  {f.relative_to(demo_dir)}")

if __name__ == '__main__':
    main()
```

### Create README Template

Create `packages/website/templates/demo-repo-readme.md.jinja`:

```jinja
# {{ title }}

{{ description }}

## What's Inside

This repository was generated by running the [Motus Get Started tutorial](https://motusos.ai/get-started/).

### Files

- `greeter.py` - A simple greeting function
- `test_greeter.py` - Tests with validation
- `cli.py` - Command-line interface
- `.motus/` - Complete audit trail

### Receipts

This demo includes **3 complete receipts** from the tutorial:

{% for feature in features %}
- **{{ feature.id }}**: {{ feature.title }}
{% endfor %}

## View the Receipts

```bash
# Install Motus
pip install motusos

# View all receipts (run from this directory)
motus work status <lease_id>
```

The `.motus/` directory contains the full audit trail including:
- Outcomes (what was delivered)
- Evidence (test results)
- Decisions (why choices were made)

## Learn More

- [How It Works](https://motusos.ai/how-it-works/)
- [Implementation Guide](https://motusos.ai/implementation/)
- [Documentation](https://motusos.ai/docs/)
```

### Publish Demo Repo

1. Generate the repo:
   ```bash
   python scripts/generate-demo-repo.py
   ```

2. Push to GitHub:
   ```bash
   cd /tmp/motus-demo-app
   git init
   git add -A
   git commit -m "Initial commit from tutorial"
   gh repo create motus-os/motus-demo-app --public --source=. --push
   ```

3. Create release ZIP:
   ```bash
   zip -r motus-demo-app.zip /tmp/motus-demo-app
   gh release create v1.0.0 motus-demo-app.zip --repo motus-os/motus-demo-app
   ```

---

### Files Touched (Tutorial)

```
packages/website/src/pages/get-started.astro       # Complete rewrite
packages/website/src/data/get-started-steps.js    # Can be removed (replaced by tutorial.yaml)
packages/website/src/data/tutorial.yaml           # NEW - source of truth
scripts/validate-tutorial.py                       # NEW - CI validation
.github/workflows/validate-tutorial.yml            # NEW - CI workflow
packages/website/vhs-scripts/tutorial-*.tape       # NEW - GIF scripts
packages/website/public/assets/tutorial/*.gif      # NEW - generated GIFs
```

---

## No Conflicts

These workstreams are parallel-safe:

| Shared | Ecosystem Uses | Tutorial Uses |
|--------|---------------|---------------|
| `lib/status.js` | Status badges for nodes | Status badges for steps |
| Status terminology | current/building/future | current/building/future |
| Visual treatment | solid/dashed/dotted | inherits same |

No file overlap. Both reinforce truth-first principles.

---

## Execution Order

```
1. Ecosystem Batch A-1 (data + gates)      ← Start here
2. Ecosystem Batch A-2 (UI flow)
3. Ecosystem Batch A-3 (defaults + polish)
4. Tutorial: Update get-started.astro      ✅ DONE
5. Tutorial: Generate GIFs                 ← PENDING (see instructions above)
6. Tutorial: Create demo repo              ← PENDING (see instructions above)
```

---

## Release Gate Integration

Both workstreams add to the release checklist:

```markdown
## Ecosystem Map
- [ ] `python scripts/check_ecosystem_map.py` passes
- [ ] All lanes have positions
- [ ] External nodes have motus_adds
- [ ] Future nodes not marked prominent

## Tutorial
- [ ] `python scripts/validate-tutorial.py` passes
- [ ] All current steps execute successfully
- [ ] GIFs regenerated if commands changed
- [ ] Demo repo generates without errors
```

---

## Questions for Implementation

None. All decisions made. Proceed with Ecosystem Batch A-1.

---

## Success Metrics

### Ecosystem
- User knows where Motus fits in 5 seconds
- Status is visually obvious without reading
- External logos answer "so what"

### Tutorial
- User builds something real
- User sees accumulated receipts
- User downloads complete demo repo
- Aha moment: "This is what my agents should produce"
