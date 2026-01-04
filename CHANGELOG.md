# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-30

Initial public release of Motus CLI - local-first agent coordination tooling.

### Added

- **`motus list`** - List available work items for discovery
- **`motus claim`** - Claim work and create a time-bounded lease for resource coordination
- **`motus release`** - Release work when complete, ending the lease
- **`motus status`** - View active leases and current work state
- **`motus install`** - Fresh install support with automatic database creation on first run

### Technical

- Python 3.9+ support
- SQLite-based local persistence (no external services required)
- Fully local operation - zero cloud dependencies
- Available via PyPI: `pip install motusos`

### Known Limitations

The following are documented limitations for v0.1.0. Fixes planned for v0.1.1:

- Attempts table not populated on claim (audit trail incomplete)
- Some evidence types may fail persistence
- Work ID not persisted across sessions
- Draft decision workflow not available (use `record_decision` directly)

See [GitHub Issues](https://github.com/motus-os/motus/issues) for tracking.
