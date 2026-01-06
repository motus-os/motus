# CLI Documentation Best Practices

> Research summary for Motus documentation

## The Golden Rule

**Examples First, Theory Second**

> "When reading a CLI's documentation, many users don't pay much attention to the synopsis syntax and go straight to the examples." - clig.dev

---

## What Users Love

1. **Immediate success** - Working example in <2 minutes
2. **Real examples** - Not placeholders, actual values
3. **Visual feedback** - See what it looks like before installing
4. **Escape hatches** - How to override smart defaults
5. **Trustworthy** - Every example is tested and works

---

## Minimum Viable Documentation

### Must-Have (Launch Blockers)

1. **README.md**
   - Installation (1-3 methods max)
   - Quick start (3-5 commands)
   - Link to full docs

2. **Built-in Help**
   - `--help` matches README examples
   - Each subcommand has help text

3. **CHANGELOG.md**
   - Version history
   - Breaking changes highlighted

### Quick Reference (Week 1)

```markdown
# Motus Quick Reference

## Most Common Commands
motus                    # Launch dashboard
motus watch abc123       # Watch specific session
motus list               # List all sessions

## Keyboard Shortcuts
j/k     Navigate
Enter   Select
f       Filter
q       Quit

## Configuration
~/.motus/config.json  # Global config
.motus/config.json    # Project config
```

---

## Command Example Format

**Good:**
```bash
# What this does
motus watch abc123
```

**Bad:**
```bash
motus watch <session-id>  # Too abstract
```

---

## CLI Help Text Pattern

```bash
$ motus --help
Motus - See what your AI agents are thinking

USAGE:
    motus [OPTIONS] [COMMAND]

COMMANDS:
    (none)      Launch TUI dashboard
    web         Launch web dashboard
    list        List all sessions
    watch       Watch specific session

EXAMPLES:
    motus                           # Launch dashboard
    motus watch abc123              # Watch session
    motus list --max-age-hours=24   # Recent sessions

See full docs: https://github.com/motus-os/motus
```

---

## Troubleshooting Section

Every CLI needs this:

```markdown
## Common Issues

### "No sessions found"
- Check if Claude Code has been run: `ls ~/.claude/projects/`
- Try: `motus list --max-age-hours=168` (1 week)

### TUI rendering issues
- Set `TERM=xterm-256color`
- Try: `motus --no-color`
```

---

## Testing Documentation

**The Iron Rule:**
> Test each example exactly as it's written. If the command doesn't work, update the docs.

How to test:
1. Copy every example from docs
2. Paste into fresh terminal
3. Verify output matches docs
4. If it fails, fix the docs (or the code!)

---

## Competitive Analysis

| Tool | README | Quick Start | Visual | Troubleshooting |
|------|--------|-------------|--------|-----------------|
| ripgrep | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| bat | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| fd | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Motus** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |

**Key Gaps:**
1. Visual examples (screenshots/GIFs)
2. Troubleshooting guide
3. More integration examples

---

## Action Items for v0.5.0

### Pre-Launch
- [ ] Verify `motus --help` matches README
- [ ] Test every command example
- [ ] Add one screenshot to README
- [ ] Create TROUBLESHOOTING.md

### Week 1 Post-Launch
- [ ] Create QUICK-REFERENCE.md
- [ ] Add integration examples
- [ ] Record 60-second demo

---

## Sources

- [ripgrep User Guide](https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md)
- [Command Line Interface Guidelines](https://clig.dev/)
- [bat README](https://github.com/sharkdp/bat/blob/master/README.md)
- [fd GitHub](https://github.com/sharkdp/fd)
- [GitHub CLI Manual](https://cli.github.com/manual/)

---

*Generated from research agent analysis - 2025-12-22*
