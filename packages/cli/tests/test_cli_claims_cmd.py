from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from motus.motus_fs import create_motus_tree


def _write_acl(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "namespaces:",
                "  motus-core:",
                "    agents:",
                "      - pattern: \"builder-*\"",
                "        permission: write",
                "  emmaus:",
                "    agents:",
                "      - pattern: \"emmaus-*\"",
                "        permission: write",
                "global_admins:",
                "  - pattern: \"opus-*\"",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_cli_claims_acquire_and_list_respects_acl(tmp_path: Path, monkeypatch, capsys) -> None:
    motus_dir = tmp_path / ".motus"
    motus_dir.mkdir()
    create_motus_tree(motus_dir)

    acl_path = motus_dir / "project" / "config" / "namespace-acl.yaml"
    _write_acl(acl_path)

    monkeypatch.chdir(tmp_path)
    from motus.cli.core import main

    with patch(
        "sys.argv",
        [
            "motus",
            "claims",
            "acquire",
            "--namespace",
            "motus-core",
            "--resource",
            "test-resource",
            "--agent",
            "builder-1",
            "--json",
        ],
    ):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["claim"]["namespace"] == "motus-core"

    with patch("sys.argv", ["motus", "claims", "list", "--agent", "builder-1", "--json"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0

    listed = json.loads(capsys.readouterr().out)
    assert listed["success"] is True
    assert len(listed["claims"]) == 1
    assert listed["claims"][0]["namespace"] == "motus-core"

    with patch(
        "sys.argv",
        [
            "motus",
            "claims",
            "acquire",
            "--namespace",
            "motus-core",
            "--resource",
            "test-resource",
            "--agent",
            "emmaus-1",
            "--json",
        ],
    ):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 2

    denied = json.loads(capsys.readouterr().out)
    assert denied["success"] is False
    assert "not authorized" in denied["message"]

