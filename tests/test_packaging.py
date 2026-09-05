from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_and_product_entry_points_are_packaged():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = metadata["project"]["scripts"]

    assert scripts["hermes"] == "hermes_cli.main:main"
    assert scripts["interfaze-api"] == "server.api_cli:main"
    assert scripts["interfaze-agent-run"] == "server.agent_runner:main"


def test_product_container_validates_its_dedicated_runner():
    dockerfile = (ROOT / "Dockerfile.interfaze-api").read_text(encoding="utf-8")

    assert "test -x /opt/venv/bin/interfaze-agent-run" in dockerfile
    assert "shutil.which(AGENT_RUNNER_EXECUTABLE)" in (
        ROOT / "server" / "app.py"
    ).read_text(encoding="utf-8")
