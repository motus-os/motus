# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class AgentRule:
    pattern: str
    permission: str


@dataclass(frozen=True, slots=True)
class NamespaceACL:
    """Namespace access control list for coordination claims."""

    namespaces: dict[str, list[AgentRule]]
    global_admins: list[AgentRule]

    @staticmethod
    def _match(agent_id: str, rule: AgentRule) -> bool:
        from fnmatch import fnmatch

        return fnmatch(agent_id, rule.pattern)

    def is_global_admin(self, agent_id: str) -> bool:
        return any(self._match(agent_id, rule) for rule in self.global_admins)

    def can_access(self, agent_id: str, namespace: str) -> bool:
        if self.is_global_admin(agent_id):
            return True
        rules = self.namespaces.get(namespace, [])
        return any(self._match(agent_id, rule) for rule in rules)

    def get_allowed_namespaces(self, agent_id: str) -> list[str]:
        if self.is_global_admin(agent_id):
            return sorted(self.namespaces.keys())
        allowed: list[str] = []
        for namespace, rules in self.namespaces.items():
            if any(self._match(agent_id, rule) for rule in rules):
                allowed.append(namespace)
        return sorted(allowed)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NamespaceACL":
        raw_namespaces = payload.get("namespaces", {}) or {}
        namespaces: dict[str, list[AgentRule]] = {}
        for namespace, cfg in raw_namespaces.items():
            rules: list[AgentRule] = []
            for agent in (cfg or {}).get("agents", []) or []:
                rules.append(
                    AgentRule(
                        pattern=str(agent.get("pattern", "")),
                        permission=str(agent.get("permission", "")),
                    )
                )
            namespaces[str(namespace)] = rules

        global_admins = [
            AgentRule(pattern=str(entry.get("pattern", "")), permission="admin")
            for entry in (payload.get("global_admins", []) or [])
        ]
        return cls(namespaces=namespaces, global_admins=global_admins)

    @classmethod
    def from_yaml_file(cls, path: str | Path) -> "NamespaceACL":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("namespace ACL must be a mapping")
        return cls.from_dict(raw)
