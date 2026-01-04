# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Process Detector - Cached, fail-silent process detection with a short TTL cache."""

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Set

from .config import config
from .logging import get_logger


@dataclass(frozen=True)
class AgentConfig:
    name: str
    process_name: str
    session_dir: Path
    include_cwd: bool
    lsof_extractor: Callable[[Path], Set[str]]
    require_session_dir: bool
    disable_on_pgrep_missing: bool = False
    disable_on_permission_error: bool = False


class ProcessDetector:
    def __init__(self, cache_ttl: float = 5.0, timeout: float = 0.5, cache_path: Path | None = None):
        self._cache: dict[str, Set[str]] = {}
        self._cache_time = 0.0
        self._enabled = True
        self._cache_ttl = cache_ttl
        self._timeout = timeout
        self._cache_path = cache_path or (config.paths.state_dir / "process_detector_cache.json")
        self._logger = get_logger(__name__)
        self._agent_configs = (
            AgentConfig("claude", "claude", config.paths.projects_dir, False, self._extract_claude_project, False, True, True),
            AgentConfig("gemini", "gemini", Path.home() / ".gemini" / "tmp", True, self._extract_gemini_project, True),
            AgentConfig("codex", "codex", Path.home() / ".codex" / "sessions", True, self._extract_codex_project, True),
        )

    def get_running_projects(self) -> Set[str]:
        if not self._enabled:
            return self._cache.get("projects", set())
        now = time.time()
        if now - self._cache_time < self._cache_ttl:
            return self._cache.get("projects", set())
        cached = self._read_disk_cache(now)
        if cached is not None:
            self._cache["projects"] = cached
            self._cache_time = now
            return cached
        projects: Set[str] = set()
        for agent in self._agent_configs:
            if not self._enabled:
                break
            try:
                projects.update(self._detect_agent_projects(agent))
            except (OSError, subprocess.SubprocessError, ValueError) as e:
                self._logger.warning(
                    "Agent detection failed",
                    agent=agent.name,
                    error_type=type(e).__name__,
                    error=str(e),
                )
        self._cache["projects"] = projects
        self._cache_time = now
        self._write_disk_cache(projects, now)
        self._logger.debug("Detected running projects across all CLIs", count=len(projects))
        return self._cache.get("projects", set())
    def is_project_active(self, project_path: str) -> bool:
        running = self.get_running_projects()
        return project_path in running or any(project_path in project for project in running)
    def is_degraded(self) -> bool:
        return not self._enabled
    def reset(self) -> None:
        self._cache.clear()
        self._cache_time = 0.0
        self._enabled = True
    def _detect_agent_projects(self, agent: AgentConfig) -> Set[str]:
        projects = self._detect_via_pgrep(agent)
        if not agent.require_session_dir or agent.session_dir.exists():
            projects.update(self._detect_via_lsof(agent))
        return projects
    def _detect_via_pgrep(self, agent: AgentConfig) -> Set[str]:
        projects: Set[str] = set()
        for line in self._run_pgrep(agent):
            projects.update(self._extract_projects_from_command(line, agent.include_cwd))
        return projects
    def _run_pgrep(self, agent: AgentConfig) -> list[str]:
        try:
            result = subprocess.run(["pgrep", "-fl", agent.process_name], capture_output=True, text=True, timeout=self._timeout)
        except subprocess.TimeoutExpired as e:
            self._logger.warning("Process detection timed out", process_type=agent.name, error_type=type(e).__name__, error=str(e))
            return []
        except PermissionError as e:
            self._logger.warning("Process detection permission denied, disabling", process_type=agent.name, error_type=type(e).__name__, error=str(e))
            if agent.disable_on_permission_error:
                self._enabled = False
            return []
        except FileNotFoundError as e:
            self._logger.warning("pgrep not available on this system", process_type=agent.name, error_type=type(e).__name__, error=str(e))
            if agent.disable_on_pgrep_missing:
                self._enabled = False
            return []
        except (OSError, subprocess.SubprocessError) as e:
            self._logger.warning("Process detection error", process_type=agent.name, error_type=type(e).__name__, error=str(e))
            return []
        if result.returncode != 0 or not result.stdout:
            return []
        return result.stdout.splitlines()
    def _detect_via_lsof(self, agent: AgentConfig) -> Set[str]:
        try:
            result = subprocess.run(["lsof", "+D", str(agent.session_dir)], capture_output=True, text=True, timeout=self._timeout)
        except subprocess.TimeoutExpired as e:
            self._logger.warning("lsof timed out", process_type=agent.name, path=str(agent.session_dir), error_type=type(e).__name__, error=str(e))
            return set()
        except (OSError, subprocess.SubprocessError) as e:
            self._logger.warning("lsof failed", process_type=agent.name, path=str(agent.session_dir), error_type=type(e).__name__, error=str(e))
            return set()
        if not result.stdout:
            return set()
        projects: Set[str] = set()
        for path in self._iter_lsof_paths(result.stdout, agent.session_dir):
            projects.update(agent.lsof_extractor(path))
        return projects
    @staticmethod
    def _extract_projects_from_command(line: str, include_cwd: bool) -> Set[str]:
        parts = line.split()
        projects: Set[str] = set()
        for i, part in enumerate(parts):
            if part in ("-p", "--project") and i + 1 < len(parts):
                projects.add(parts[i + 1])
            if include_cwd and part in ("--cwd", "-C") and i + 1 < len(parts):
                projects.add(parts[i + 1])
        return projects
    @staticmethod
    def _iter_lsof_paths(output: str, session_dir: Path) -> Iterable[Path]:
        session_dir_str = str(session_dir)
        for line in output.splitlines():
            if session_dir_str not in line:
                continue
            for part in line.split():
                if session_dir_str in part:
                    yield Path(part)

    def _extract_claude_project(self, path: Path) -> Set[str]:
        try:
            rel_path = path.relative_to(config.paths.projects_dir)
        except ValueError:
            return set()
        return {rel_path.parts[0]} if rel_path.parts else set()

    def _extract_gemini_project(self, path: Path) -> Set[str]:
        if "chats" not in path.parts:
            return set()
        try:
            rel_path = path.relative_to(Path.home() / ".gemini" / "tmp")
        except ValueError:
            return set()
        return {f"gemini:{rel_path.parts[0]}"} if rel_path.parts else set()

    def _extract_codex_project(self, path: Path) -> Set[str]:
        if path.suffix != ".jsonl":
            return set()
        try:
            if not path.exists():
                return set()
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                first_line = handle.readline().strip()
            if not first_line:
                return set()
            data = json.loads(first_line)
            if data.get("type") != "session_meta":
                return set()
            cwd = data.get("payload", {}).get("cwd", "")
            return {cwd} if cwd else set()
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, IndexError) as e:
            self._logger.warning(
                "Failed to parse Codex session metadata",
                file_path=str(path),
                error_type=type(e).__name__,
                error=str(e),
            )
            return set()

    def _read_disk_cache(self, now: float) -> Set[str] | None:
        if self._cache_ttl <= 0:
            return None
        try:
            data = json.loads(self._cache_path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            self._logger.warning(
                "Process detector cache read failed",
                path=str(self._cache_path),
                error_type=type(e).__name__,
                error=str(e),
            )
            return None
        if not isinstance(data, dict):
            return None
        timestamp = data.get("timestamp")
        projects = data.get("projects")
        if not isinstance(timestamp, (int, float)) or now - timestamp >= self._cache_ttl:
            return None
        if not isinstance(projects, list):
            return None
        return {project for project in projects if isinstance(project, str)}

    def _write_disk_cache(self, projects: Set[str], now: float) -> None:
        if self._cache_ttl <= 0:
            return
        try:
            payload = {"timestamp": now, "projects": sorted(projects)}
            self._cache_path.write_text(json.dumps(payload))
        except OSError as e:
            self._logger.warning("Process detector cache write failed", path=str(self._cache_path), error_type=type(e).__name__, error=str(e))
