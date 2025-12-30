"""Conformance tests for Motus Coordination API.

These tests validate the API against TEST_PLAN.md section 1.1:
- Contention: two agents race a write claim → one GRANTED, one BUSY_WRITE_HELD
- TTL expiry: lease expires → rollback → resource claimable
- Release idempotency: release twice → RELEASED_IDEMPOTENT_REPLAY
- Capability gating: write without lease → DENY_MISSING_LEASE
"""
