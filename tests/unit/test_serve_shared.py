"""serve_shared.sh: help, tunnel refusal, local start."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from searcher.api.main import create_app
from searcher.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "serve_shared.sh"


def _bash() -> str:
    found = shutil.which("bash")
    assert found is not None
    return found


def test_help_lists_modes_and_warns() -> None:
    result = subprocess.run(
        [_bash(), str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    text = result.stdout.lower()
    assert "--lan" in result.stdout
    assert "--tunnel" in result.stdout
    assert "unauthenticated" in text
    assert "?api=" in text or "api=" in text


def test_tunnel_refuses_without_cloudflared(tmp_path: Path) -> None:
    env = os.environ.copy()
    # Keep bash/coreutils; omit Homebrew so a machine-local cloudflared is hidden.
    env["PATH"] = os.pathsep.join([str(tmp_path), "/bin", "/usr/bin"])
    result = subprocess.run(
        [_bash(), str(SCRIPT), "--tunnel"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "cloudflared is not installed" in combined
    assert "will not install" in combined


def test_local_start_serves_health(tmp_path: Path, monkeypatch: object) -> None:
    """The script execs `searcher serve`; the app it starts must answer health."""
    monkeypatch.setenv("SEARCHER_SERVE_WEB", "1")  # type: ignore[attr-defined]
    settings = Settings.from_env(data_root=tmp_path / "data")
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in {"ok", "degraded"}
        assert body["api"] == "up"
        assert "blocked_lanes" in body
        assert "lanes" in body
