# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

We take the security of Motus seriously. If you believe you have found a security vulnerability, please report it to us as described below.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via GitHub Security Advisories:
**https://github.com/motus-os/motus/security/advisories**

You should receive a response within 48 hours.

Please include the requested information listed below (as much as you can provide) to help us better understand the nature and scope of the possible issue:

* Type of issue (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
* Full paths of source file(s) related to the manifestation of the issue
* The location of the affected source code (tag/branch/commit or direct URL)
* Any special configuration required to reproduce the issue
* Step-by-step instructions to reproduce the issue
* Proof-of-concept or exploit code (if possible)
* Impact of the issue, including how an attacker might exploit the issue

This information will help us triage your report more quickly.

## Preferred Languages

We prefer all communications to be in English.

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine the affected versions
2. Audit code to find any potential similar problems
3. Prepare fixes for all supported versions
4. Release new versions and publish advisories

## Security Best Practices

When using Motus:

* **Session Data**: Motus reads Claude Code session files from `~/.claude/projects/`. These may contain sensitive information about your codebase. Motus does not transmit this data anywhere.
* **Hooks**: The `motus install-hooks` command modifies your Claude Code settings. Review the changes before approving.
* **Web Dashboard**: The web dashboard runs on localhost only by default. Do not expose it to public networks.
* **Trace Files**: SDK trace files stored in `~/.motus/traces/` may contain sensitive information. Secure this directory appropriately.

## Dependency Update Policy

- Dependabot manages dependency updates for `/packages/cli` and `/packages/website`.
- Security updates auto-merge after CI passes.
- Minor updates are batched weekly.
- Major updates require manual review (Dependabot ignores semver-major updates by default).

## Known Limitations (Accepted Risks)

The following issues have been reviewed and **explicitly accepted** as low-risk for a localhost-only developer tool. Do not re-review these unless the threat model changes.

### 1. Path Reconstruction (`extract_project_path`)
- **Location:** `src/motus/commands/utils.py:73-120`
- **Issue:** String manipulation to decode `-Users-ben-GitHub-project` format
- **Why Accepted:** Directory names come from Claude Code's own encoding. Attacker would need to compromise Claude Code itself.

### 2. Session ID Validation
- **Location:** `src/motus/ui/web.py` WebSocket handlers
- **Issue:** No strict UUID format validation
- **Why Accepted:** Session IDs come from local filesystem transcripts the user already trusts.

### 3. innerHTML Usage in Dashboard
- **Location:** `src/motus/ui/web.py` JavaScript section
- **Issue:** Dynamic content via innerHTML (with escapeHtml)
- **Why Accepted:** All content passes through `escapeHtml()`. Source is local transcripts.

### 4. No WebSocket Authentication
- **Location:** `src/motus/ui/web.py`
- **Issue:** WebSocket accepts connections without auth
- **Why Accepted:** Default binding is 127.0.0.1. Users who override `MC_HOST=0.0.0.0` accept that risk.

### 5. Secret Redaction Coverage Gaps
- **Location:** `src/motus/commands/utils.py:18-31`
- **Issue:** Not all secret patterns detected (Google API keys, Azure keys, etc.)
- **Why Accepted:** Defense-in-depth for user's own data. Users should not rely solely on redaction.

### Decision Log

| Date | Reviewer | Decision |
|------|----------|----------|
| 2024-12-01 | Internal review | Accept all 5 items above as localhost-only tool risks |

**For future reviewers:** These have been evaluated. Stop here unless adding network deployment support.

---

## Comments on this Policy

If you have suggestions on how this process could be improved, please submit a pull request.
