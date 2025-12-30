# Motus Command - Website Design Spec

> Design specification for motusos.ai

## Design Principles
- **Minimal & Fast**: Single-page navigation, progressive enhancement
- **Dark First**: Veritas-inspired color palette with mint accents
- **Developer-Focused**: Code-first presentation, terminal aesthetics
- **Trust Through Transparency**: Local-first messaging, no tracking

---

## Color Palette

```css
--motus-dark-bg: #0A0A0F        /* Deep space black */
--motus-surface: #14141E        /* Card/panel surface */
--motus-border: #2A2A3A         /* Subtle borders */
--motus-mint: #5AE6C8           /* Primary accent */
--motus-purple: #AB45C0         /* Secondary accent */
--motus-text: #E5E5F0           /* Body text */
--motus-text-dim: #9090A0       /* Muted text */
--motus-green: #4ADE80          /* Success/safe */
--motus-yellow: #FACC15         /* Warning */
--motus-red: #F87171            /* Danger */
```

---

## MVP Site Structure (3 Pages)

```
motusos.ai/
├── index.html              # Hero + features + quick start + FAQ
├── docs.html              # Single-page documentation (anchor navigation)
└── changelog.html         # Release history
```

---

## Homepage Structure

```
┌────────────────────────────────────────────────────────┐
│ [mc] Motus Command                    [Docs] [GitHub]  │
├────────────────────────────────────────────────────────┤
│                    HERO SECTION                         │
│   "See What Your AI Agents Are Thinking"               │
│   [Animated terminal showing live agent trace]         │
│   pip install motusos                                  │
│   [Get Started →]  [View Docs]                         │
├────────────────────────────────────────────────────────┤
│                TRUST BAR (3 pillars)                    │
│   [Local-First]    [Multi-Agent]    [Developer-First]  │
├────────────────────────────────────────────────────────┤
│                   FEATURES (Grid)                       │
│   📊 Trace Plane    🔄 Teleport      🛡️ Governance     │
│   🌐 Web UI         🐍 Python SDK    👁️ Awareness      │
├────────────────────────────────────────────────────────┤
│              WHY MOTUS? (Kernel Message)                │
│   "Motus is the local-first agent kernel..."           │
│   [Read the Manifesto →]                               │
├────────────────────────────────────────────────────────┤
│                   FOOTER                                │
│   MIT License | GitHub | PyPI | Docs                    │
└────────────────────────────────────────────────────────┘
```

---

## Technical Stack

**Recommendation: VitePress** (Vue-based, fast, dark mode native)
- Alternative: Astro (less JS)
- Alternative: Plain HTML + CSS (smallest)

**Deployment: Cloudflare Pages**
- Zero-config, CDN, free SSL
- Build: `npm run build`
- Output: `docs/.vitepress/dist`

---

## Performance Budget

| Metric | Target |
|--------|--------|
| First Paint | < 500ms |
| Page Size | < 200KB |
| Lighthouse | 100/100 |
| Build Time | < 5s |

---

## Typography

```css
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;
--font-sans: 'Inter', -apple-system, system-ui, sans-serif;

h1: 48px, font-mono, mint gradient
h2: 36px, font-sans
body: 16px, font-sans
code: 14px, font-mono
```

---

## Terminal Animation (Hero)

Auto-typing effect showing:
```
$ pip install motusos
$ mc
```

Then live feed scrolls with sample events:
```
12:59:20 [BASH] pip install -e .
12:59:20 [THINK] Let me check if...
12:59:21 [DECIDE] Using SQLite for...
12:59:51 [SPAWN] general-purpose
```

Colors: BASH (red), THINK (dim), DECIDE (mint), SPAWN (purple)

---

## Launch Checklist

### Pre-Launch
- [ ] Domain: motusos.ai
- [ ] Cloudflare Pages connected
- [ ] SSL provisioned

### Content
- [ ] Homepage complete
- [ ] Getting Started
- [ ] Commands reference
- [ ] Changelog

### Assets
- [ ] Logo (SVG)
- [ ] Favicon
- [ ] TUI screenshot
- [ ] OG image (1200x630px)

### Performance
- [ ] Lighthouse 100
- [ ] First paint < 500ms
- [ ] Total size < 200KB

---

## Key Messaging

**Tagline:** "See What Your AI Agents Are Thinking"

**Trust Pillars:**
1. Local-First (no cloud required)
2. Multi-Agent (Claude, Codex, Gemini)
3. Developer-First (Terminal + Web)

**Differentiator:** "The 6 Kernel Primitives"
- Trace Plane
- Teleport
- Awareness
- SDK
- Governance
- Sovereignty

---

*Generated from research agent analysis - 2025-12-22*
