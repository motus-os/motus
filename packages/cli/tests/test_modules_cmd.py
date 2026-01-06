from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def _write_registry(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                'version: "1.0"',
                "status_semantics:",
                '  current: "Implemented + documented + runnable example."',
                "kernel:",
                "  id: kernel",
                '  marketing_name: "Motus Kernel"',
                "  scope: kernel",
                "  status: current",
                "  roadmap_id: null",
                '  target_release: "v0.1.0"',
                '  description: "Deterministic coordination layer."',
                "bundled_modules:",
                "  - id: module-sdk",
                '    marketing_name: "Module SDK"',
                "    scope: bundled",
                "    status: building",
                '    roadmap_id: "RI-MOD-001"',
                "    target_release: null",
                '    description: "Interfaces and toggles for modules."',
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_modules_list_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry_path = tmp_path / "module-registry.yaml"
    _write_registry(registry_path)

    with patch(
        "sys.argv",
        [
            "motus",
            "modules",
            "list",
            "--registry",
            str(registry_path),
            "--json",
        ],
    ):
        from motus.cli.core import main

        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 0
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["registry_version"] == "1.0"
    assert payload["count"] == 2
    assert [m["id"] for m in payload["modules"]] == ["kernel", "module-sdk"]
