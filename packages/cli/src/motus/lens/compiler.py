# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Lens compiler (Tier 0)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Protocol, TypedDict

from motus.coordination.schemas import ClaimedResource as Resource
from motus.coordination.schemas.common import _iso_z

_TIER0_TOTAL_TOKENS = 300
_TIER0_METADATA_RESERVE = 40
_TIER0_BUDGETS = {
    "resource_specs": 110,
    "policy_snippets": 60,
    "tool_guidance": 50,
    "recent_outcomes": 40,
    "warnings": _TIER0_METADATA_RESERVE,
}
_OUTCOME_LIMIT = 25
_TOKEN_CHARS = 4
_MAX_STR_LEN = 200
_BUDGET_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?\s*$")


class LensItem(TypedDict, total=False):
    source_type: str
    source_id: str
    source_hash: str
    cache_state_hash: str
    observed_at: str
    staleness_model: str
    staleness_age_s: int | None
    authority: str
    payload: dict[str, Any]


class LensPacket(TypedDict):
    lens_version: str
    tier: str
    policy_version: str
    intent: str
    cache_state_hash: str
    assembled_at: str
    lens_hash: str
    warnings: list[LensItem]
    resource_specs: list[LensItem]
    policy_snippets: list[LensItem]
    tool_guidance: list[LensItem]
    recent_outcomes: list[LensItem]


class ContextCacheReader(Protocol):
    def get_resource_spec(self, resource: Resource) -> dict[str, Any] | None:
        ...

    def get_policy_bundle(self, policy_version: str) -> dict[str, Any] | None:
        ...

    def get_tool_specs(self, tool_names: list[str]) -> list[dict[str, Any]] | dict[str, dict[str, Any]]:
        ...

    def get_recent_outcomes(self, resources: list[Resource], limit: int) -> list[dict[str, Any]]:
        ...


_CACHE_READER: ContextCacheReader | None = None


def set_cache_reader(reader: ContextCacheReader) -> None:
    """Register the Context Cache adapter used by the Lens compiler."""
    global _CACHE_READER
    _CACHE_READER = reader


def assemble_lens(
    policy_version: str,
    resources: list[Resource],
    intent: str,
    cache_state_hash: str,
    timestamp: datetime,
) -> LensPacket:
    """Deterministic assembly of context for a task.

    See specs/lens-compiler-v1.md for Tier 0 rules, budgets, and provenance tagging.
    """
    _require_non_empty(policy_version, "policy_version")
    _require_non_empty(intent, "intent")
    _require_non_empty(cache_state_hash, "cache_state_hash")
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    cache = _get_cache_reader()
    normalized_resources = _normalize_resources(resources)
    assembled_at = _iso_z(timestamp)

    warnings: list[LensItem] = []
    resource_specs: list[LensItem] = []
    for resource in normalized_resources:
        entry = cache.get_resource_spec(resource)
        if entry is None:
            warnings.append(
                _warning_item(
                    f"ResourceSpec missing for {resource.type}:{resource.path}",
                    cache_state_hash,
                    assembled_at,
                )
            )
            continue
        payload, meta = _split_entry(entry)
        staleness_model, staleness_age_s, staleness_budget_s = _resource_staleness(
            payload, meta, timestamp
        )
        if staleness_model == "unknown":
            warnings.append(
                _warning_item(
                    f"Unknown staleness model for {resource.type}:{resource.path}",
                    cache_state_hash,
                    assembled_at,
                )
            )
        if (
            staleness_budget_s is not None
            and staleness_age_s is not None
            and staleness_age_s > staleness_budget_s
        ):
            warnings.append(
                _warning_item(
                    (
                        "Staleness budget exceeded for "
                        f"{resource.type}:{resource.path} "
                        f"(age_s={staleness_age_s}, budget_s={staleness_budget_s})"
                    ),
                    cache_state_hash,
                    assembled_at,
                )
            )
        resource_specs.append(
            _lens_item(
                source_type="resource_spec",
                source_id=str(meta.get("source_id") or payload.get("id") or resource.path),
                payload=payload,
                cache_state_hash=cache_state_hash,
                observed_at=assembled_at,
                staleness_model=staleness_model,
                staleness_age_s=staleness_age_s,
                authority=_authority_for_item(meta, "authoritative"),
                source_hash=str(meta.get("source_hash") or _hash_payload(payload)),
            )
        )

    policy_bundle_entry = cache.get_policy_bundle(policy_version)
    policy_payload: dict[str, Any] | None = None
    policy_meta: dict[str, Any] = {}
    policy_snippets: list[LensItem] = []
    if policy_bundle_entry is None:
        warnings.append(
            _warning_item(
                f"Policy bundle missing for version {policy_version}",
                cache_state_hash,
                assembled_at,
            )
        )
    else:
        policy_payload, policy_meta = _split_entry(policy_bundle_entry)
        policy_snippets = _policy_items_from_bundle(
            policy_payload,
            policy_meta,
            cache_state_hash,
            assembled_at,
            timestamp,
            policy_version,
        )

    tool_guidance: list[LensItem] = []
    tool_names = _collect_tool_names(policy_payload, normalized_resources)
    if tool_names:
        tool_specs = cache.get_tool_specs(tool_names)
        tool_entries = _normalize_tool_specs(tool_specs)
        if not tool_entries:
            warnings.append(
                _warning_item(
                    f"Tool specs missing for {', '.join(tool_names)}",
                    cache_state_hash,
                    assembled_at,
                )
            )
        else:
            tool_guidance, missing_tools = _tool_items_from_entries(
                tool_entries,
                cache_state_hash,
                assembled_at,
                timestamp,
                tool_names,
            )
            if missing_tools:
                warnings.append(
                    _warning_item(
                        f"Tool specs missing for {', '.join(sorted(missing_tools))}",
                        cache_state_hash,
                        assembled_at,
                    )
                )

    recent_outcomes: list[LensItem] = []
    outcomes = cache.get_recent_outcomes(normalized_resources, limit=_OUTCOME_LIMIT)
    if outcomes:
        recent_outcomes = _outcome_items_from_entries(
            outcomes,
            cache_state_hash,
            assembled_at,
            timestamp,
        )

    warnings = _trim_to_budget(_sorted_items(warnings), _TIER0_BUDGETS["warnings"])
    resource_specs = _trim_to_budget(_sorted_items(resource_specs), _TIER0_BUDGETS["resource_specs"])
    policy_snippets = _trim_to_budget(_sorted_items(policy_snippets), _TIER0_BUDGETS["policy_snippets"])
    tool_guidance = _trim_to_budget(_sorted_items(tool_guidance), _TIER0_BUDGETS["tool_guidance"])
    recent_outcomes = _trim_to_budget(
        _sorted_outcomes(recent_outcomes), _TIER0_BUDGETS["recent_outcomes"]
    )

    packet: LensPacket = {
        "lens_version": "v1",
        "tier": "tier0",
        "policy_version": policy_version,
        "intent": intent,
        "cache_state_hash": cache_state_hash,
        "assembled_at": assembled_at,
        "lens_hash": "",
        "warnings": warnings,
        "resource_specs": resource_specs,
        "policy_snippets": policy_snippets,
        "tool_guidance": tool_guidance,
        "recent_outcomes": recent_outcomes,
    }
    packet["lens_hash"] = _hash_payload(packet)
    return packet


def _get_cache_reader() -> ContextCacheReader:
    if _CACHE_READER is None:
        raise RuntimeError("Context Cache reader is not configured")
    return _CACHE_READER


def _require_non_empty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _normalize_resources(resources: list[Resource]) -> list[Resource]:
    normalized: list[Resource] = []
    seen: set[tuple[str, str]] = set()
    for res in resources:
        if isinstance(res, Resource):
            resource = res
        elif isinstance(res, dict) and "type" in res and "path" in res:
            resource = Resource(type=str(res["type"]), path=str(res["path"]))
        else:
            raise ValueError("resources must be ClaimedResource instances or {type, path} dicts")
        key = (resource.type, resource.path)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(resource)
    normalized.sort(key=lambda r: (r.type, r.path))
    return normalized


def _split_entry(entry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if "payload" in entry and isinstance(entry.get("payload"), dict):
        payload = entry["payload"]
        meta = {k: v for k, v in entry.items() if k != "payload"}
        return payload, meta
    return entry, {}


def _authority_for_item(meta: dict[str, Any], default: str) -> str:
    authority = meta.get("authority")
    if isinstance(authority, str) and authority:
        return authority
    return default


def _resource_staleness(
    payload: dict[str, Any], meta: dict[str, Any], assembled_at: datetime
) -> tuple[str, int | None, int | None]:
    consistency = payload.get("consistency_model") or payload.get("consistencyModel") or {}
    staleness_model = "unknown"
    staleness_budget_s: int | None = None
    if isinstance(consistency, dict):
        raw_model = consistency.get("staleness_model") or consistency.get("stalenessModel")
        if isinstance(raw_model, str) and raw_model:
            staleness_model = raw_model
        staleness_budget_s = _parse_budget_s(
            consistency.get("staleness_budget") or consistency.get("stalenessBudget")
        )
    if "staleness_model" in meta and isinstance(meta["staleness_model"], str):
        staleness_model = meta["staleness_model"]
    if "staleness_budget_s" in meta and isinstance(meta["staleness_budget_s"], int):
        staleness_budget_s = meta["staleness_budget_s"]

    source_ts = _extract_source_timestamp(payload, meta)
    staleness_age_s = None
    if source_ts is not None:
        staleness_age_s = max(0, int((assembled_at - source_ts).total_seconds()))
    return staleness_model, staleness_age_s, staleness_budget_s


def _extract_source_timestamp(payload: dict[str, Any], meta: dict[str, Any]) -> datetime | None:
    for key in ("observed_at", "updated_at", "last_updated_at", "timestamp", "recorded_at"):
        ts = _parse_timestamp(meta.get(key))
        if ts is not None:
            return ts
    for key in ("observed_at", "updated_at", "last_updated_at", "timestamp", "recorded_at"):
        ts = _parse_timestamp(payload.get(key))
        if ts is not None:
            return ts
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return None
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    return None


def _policy_items_from_bundle(
    payload: dict[str, Any],
    meta: dict[str, Any],
    cache_state_hash: str,
    observed_at: str,
    assembled_at: datetime,
    policy_version: str,
) -> list[LensItem]:
    policies_raw = payload.get("policies")
    if isinstance(policies_raw, list) and policies_raw:
        policy_items = policies_raw
    else:
        policy_items = [payload]
    items: list[LensItem] = []
    for idx, policy in enumerate(policy_items):
        if not isinstance(policy, dict):
            continue
        source_id = str(
            policy.get("id")
            or policy.get("policy_id")
            or policy.get("name")
            or f"{policy_version}:{idx}"
        )
        items.append(
            _lens_item(
                source_type="policy",
                source_id=source_id,
                payload=policy,
                cache_state_hash=cache_state_hash,
                observed_at=observed_at,
                staleness_model=_staleness_model_from_meta(meta),
                staleness_age_s=_staleness_age_from_meta(meta, assembled_at),
                authority=_authority_for_item(meta, "authoritative"),
                source_hash=str(_hash_payload(policy)),
            )
        )
    return items


def _tool_items_from_entries(
    entries: list[dict[str, Any]],
    cache_state_hash: str,
    observed_at: str,
    assembled_at: datetime,
    requested_names: list[str],
) -> tuple[list[LensItem], list[str]]:
    items: list[LensItem] = []
    names_seen: set[str] = set()
    for entry in entries:
        payload, meta = _split_entry(entry)
        source_id = str(payload.get("name") or payload.get("tool_name") or payload.get("id") or "")
        if not source_id:
            source_id = str(meta.get("source_id") or "")
        if not source_id:
            source_id = f"tool-{len(items)}"
        names_seen.add(source_id)
        items.append(
            _lens_item(
                source_type="tool_spec",
                source_id=source_id,
                payload=payload,
                cache_state_hash=cache_state_hash,
                observed_at=observed_at,
                staleness_model=_staleness_model_from_meta(meta),
                staleness_age_s=_staleness_age_from_meta(meta, assembled_at),
                authority=_authority_for_item(meta, "authoritative"),
                source_hash=str(meta.get("source_hash") or _hash_payload(payload)),
            )
        )
    missing = [name for name in requested_names if name not in names_seen]
    return items, missing


def _outcome_items_from_entries(
    entries: list[dict[str, Any]],
    cache_state_hash: str,
    observed_at: str,
    assembled_at: datetime,
) -> list[LensItem]:
    items: list[LensItem] = []
    for idx, entry in enumerate(entries):
        payload, meta = _split_entry(entry)
        source_id = str(payload.get("id") or payload.get("outcome_id") or f"outcome-{idx}")
        items.append(
            _lens_item(
                source_type="outcome",
                source_id=source_id,
                payload=payload,
                cache_state_hash=cache_state_hash,
                observed_at=observed_at,
                staleness_model=_staleness_model_from_meta(meta),
                staleness_age_s=_staleness_age_from_meta(meta, assembled_at),
                authority=_authority_for_item(meta, "advisory"),
                source_hash=str(meta.get("source_hash") or _hash_payload(payload)),
            )
        )
    return items


def _normalize_tool_specs(
    tool_specs: list[dict[str, Any]] | dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    if isinstance(tool_specs, dict):
        return list(tool_specs.values())
    if isinstance(tool_specs, list):
        return [spec for spec in tool_specs if isinstance(spec, dict)]
    return []


def _collect_tool_names(
    policy_payload: dict[str, Any] | None, resources: list[Resource]
) -> list[str]:
    names: set[str] = set()
    if policy_payload:
        _collect_tool_names_from_obj(policy_payload, names)
        policies = policy_payload.get("policies")
        if isinstance(policies, list):
            for policy in policies:
                if isinstance(policy, dict):
                    _collect_tool_names_from_obj(policy, names)
    for resource in resources:
        if resource.type.startswith("tool:"):
            names.add(resource.type.split(":", 1)[1])
        elif resource.type.startswith("tool/"):
            names.add(resource.type.split("/", 1)[1])
    return sorted(name for name in names if name)


def _collect_tool_names_from_obj(obj: dict[str, Any], names: set[str]) -> None:
    for key in ("tools", "tool_names", "tool_specs"):
        raw = obj.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item:
                    names.add(item)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("tool_name") or item.get("id")
                    if isinstance(name, str) and name:
                        names.add(name)


def _lens_item(
    *,
    source_type: str,
    source_id: str,
    payload: dict[str, Any],
    cache_state_hash: str,
    observed_at: str,
    staleness_model: str,
    staleness_age_s: int | None,
    authority: str,
    source_hash: str,
) -> LensItem:
    return {
        "source_type": source_type,
        "source_id": source_id,
        "source_hash": source_hash,
        "cache_state_hash": cache_state_hash,
        "observed_at": observed_at,
        "staleness_model": staleness_model,
        "staleness_age_s": staleness_age_s,
        "authority": authority,
        "payload": payload,
    }


def _warning_item(message: str, cache_state_hash: str, observed_at: str) -> LensItem:
    payload = {"message": message}
    return _lens_item(
        source_type="warning",
        source_id=_hash_payload(payload)[:12],
        payload=payload,
        cache_state_hash=cache_state_hash,
        observed_at=observed_at,
        staleness_model="unknown",
        staleness_age_s=None,
        authority="advisory",
        source_hash=_hash_payload(payload),
    )


def _sorted_items(items: list[LensItem]) -> list[LensItem]:
    return sorted(items, key=lambda item: (item.get("source_id", ""), item.get("source_hash", "")))


def _sorted_outcomes(items: list[LensItem]) -> list[LensItem]:
    def _key(item: LensItem) -> tuple[int, str]:
        payload = item.get("payload") or {}
        ts = _parse_timestamp(payload.get("occurred_at") or payload.get("observed_at"))
        if ts is None:
            return (0, str(item.get("source_id", "")))
        return (int(ts.timestamp()), str(item.get("source_id", "")))

    return sorted(items, key=_key, reverse=True)


def _trim_to_budget(items: list[LensItem], budget: int) -> list[LensItem]:
    if budget <= 0:
        return []
    total = 0
    trimmed: list[LensItem] = []
    for item in items:
        item = _truncate_item(item)
        cost = _estimate_tokens(item)
        if total + cost > budget:
            break
        trimmed.append(item)
        total += cost
    return trimmed


def _truncate_item(item: LensItem) -> LensItem:
    payload = item.get("payload")
    if not isinstance(payload, dict):
        return item
    truncated_payload = dict(payload)
    for key, value in payload.items():
        if isinstance(value, str) and len(value) > _MAX_STR_LEN:
            truncated_payload[key] = value[:_MAX_STR_LEN] + "..."
    if truncated_payload == payload:
        return item
    truncated = dict(item)
    truncated["payload"] = truncated_payload
    return truncated


def _estimate_tokens(obj: Any) -> int:
    canonical = _canonical_json(obj)
    return max(1, (len(canonical) + (_TOKEN_CHARS - 1)) // _TOKEN_CHARS)


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_payload(obj: Any) -> str:
    canonical = _canonical_json(obj)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _staleness_model_from_meta(meta: dict[str, Any]) -> str:
    model = meta.get("staleness_model")
    if isinstance(model, str) and model:
        return model
    return "unknown"


def _staleness_age_from_meta(meta: dict[str, Any], assembled_at: datetime) -> int | None:
    source_ts = _extract_source_timestamp({}, meta)
    if source_ts is None:
        return None
    return max(0, int((assembled_at - source_ts).total_seconds()))


def _parse_budget_s(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        match = _BUDGET_RE.match(value)
        if not match:
            return None
        qty = float(match.group(1))
        unit = (match.group(2) or "s").lower()
        if unit in ("s", "sec", "secs", "second", "seconds"):
            return int(qty)
        if unit in ("m", "min", "mins", "minute", "minutes"):
            return int(qty * 60)
        if unit in ("h", "hr", "hrs", "hour", "hours"):
            return int(qty * 3600)
    return None
