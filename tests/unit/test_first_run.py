"""first_run.sh self-check, weights honesty, and share-script refusals."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIRST_RUN = ROOT / "scripts" / "first_run.sh"
RUN_API = ROOT / "scripts" / "run_api.sh"
SERVE = ROOT / "scripts" / "serve_shared.sh"
README = ROOT / "README.md"

WEIGHTS_INSTALL = "uv run --extra vision python scripts/prepare_embedding_weights.py"

OPERATOR_LANES = (
    "Reading photographs",
    "Live listing discovery",
    "Result routing",
    "Learned visual backbone",
    "Optional visual donor",
    "Reading text in photographs",
    "Saving searches on disk",
)

INTERNAL_LANE_NAMES = (
    "IMAGE_DECODE",
    "DENSE_FEATURES",
    "OBJECT_SEGMENTATION",
    "LOGO_DETECTION",
    "LOCAL_CORRESPONDENCE",
    "MATERIAL_ANALYSIS",
    "BROWSER_CAPTURE",
    "WORLD_STATE",
    "NEXT_VIEW",
    "RECEIPT_VERIFY",
)


def _bash() -> str:
    found = shutil.which("bash")
    assert found is not None
    return found


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_first_run_exists_and_is_executable() -> None:
    assert FIRST_RUN.is_file()
    assert os.access(FIRST_RUN, os.X_OK)


def test_help_lists_check_only_and_warns() -> None:
    result = subprocess.run(
        [_bash(), str(FIRST_RUN), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    text = result.stdout.lower()
    assert "--check-only" in result.stdout
    assert "no authentication" in text
    assert "empty" in text


def test_script_states_weights_absent_and_install_command() -> None:
    script = _read(FIRST_RUN)
    assert "not present" in script
    assert "classical descriptors" in script
    assert "missing-weight fallback" in script
    assert WEIGHTS_INSTALL in script
    assert "Availability is a successful probe, not file existence." in script


def test_script_reports_operator_lane_names() -> None:
    script = _read(FIRST_RUN)
    for name in OPERATOR_LANES:
        assert name in script, f"missing operator lane {name!r}"
    assert 'flag = "live" if live else "blocked"' in script
    # Printed labels are the operator names, not the capability enum.
    assert '("Reading photographs"' in script
    assert '("Live listing discovery"' in script
    assert '("Result routing"' in script
    assert '("Learned visual backbone"' in script


def test_run_api_enables_live_discovery_and_states_weights() -> None:
    script = _read(RUN_API)
    assert "SEARCHER_LIVE_DISCOVERY" in script
    assert "${SEARCHER_LIVE_DISCOVERY:-1}" in script
    assert "Learned visual backbone" in script
    assert WEIGHTS_INSTALL in script
    assert "address already in use" in script
    assert "./scripts/first_run.sh" in script


def test_serve_shared_verifies_before_claiming_live() -> None:
    script = _read(SERVE)
    assert "verify_answers" in script
    assert "verify_cors" in script
    assert "address already in use" in script
    assert "Refusing to print a Pages URL" in script
    assert "mixed content" in script
    assert "WARNING: This alpha has no authentication." in script
    assert "Access-Control-Allow-Origin" in script or "access-control-allow-origin" in script


def test_readme_leads_with_first_run_and_keeps_no_auth_warning() -> None:
    text = _read(README)
    assert "./scripts/first_run.sh" in text
    assert "./scripts/first_run.sh --check-only" in text
    assert "SEARCHER_API_PORT=8766 ./scripts/first_run.sh" in text
    assert "WARNING: This alpha has no authentication." in text
    assert "no authentication" in text.lower()
    assert "learned" in text.lower()
    assert "classical descriptors" in text


def test_serve_shared_refuses_when_port_in_use() -> None:
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.listen(1)
    try:
        result = subprocess.run(
            [_bash(), str(SERVE), "--port", str(port), "--check"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    finally:
        sock.close()
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "address already in use" in combined
    assert f":{port}" in (result.stdout + result.stderr)
    assert "Verified. This URL answers" not in result.stdout


def test_serve_shared_refuses_pages_origin_with_a_path() -> None:
    env = os.environ.copy()
    env["SEARCHER_PAGES_ORIGIN"] = "https://joshuahickscorp.github.io/searcher/"
    result = subprocess.run(
        [_bash(), str(SERVE), "--check"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "origin only" in combined.lower()
    assert "Verified. This URL answers" not in result.stdout


def test_serve_shared_refuses_unusable_pages_url_on_http() -> None:
    env = os.environ.copy()
    env["SEARCHER_PAGES_URL"] = "https://joshuahickscorp.github.io/searcher/"
    env["SEARCHER_PAGES_ORIGIN"] = "https://joshuahickscorp.github.io"
    result = subprocess.run(
        [_bash(), str(SERVE), "--check"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    combined = result.stdout + result.stderr
    assert "Refusing to print a Pages URL" in combined
    assert "mixed content" in combined.lower()
    assert "Hand this to a friend" not in result.stdout
    assert "?api=https://joshuahickscorp.github.io" not in result.stdout
    assert "joshuahickscorp.github.io/searcher/?api=http://" not in combined


def test_serve_shared_help_still_warns() -> None:
    result = subprocess.run(
        [_bash(), str(SERVE), "--help"],
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
    assert "no authentication" in text


def test_check_only_reports_blocked_backbone_without_weights(tmp_path: Path) -> None:
    pytest.importorskip("searcher")
    env = os.environ.copy()
    env["SEARCHER_DATA_ROOT"] = str(tmp_path / "data")
    env.pop("SEARCHER_EMBEDDING_WEIGHTS", None)
    result = subprocess.run(
        [_bash(), str(FIRST_RUN), "--check-only"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    for name in OPERATOR_LANES:
        assert name in out, f"operator lane missing from output: {name}"
    assert "live" in out
    assert "blocked" in out
    assert "Learned visual backbone" in out
    assert "not present" in out.lower() or "blocked" in out
    assert WEIGHTS_INSTALL in out
    assert "classical descriptors" in out
    for internal in INTERNAL_LANE_NAMES:
        # Capability names must not be the printed lane labels.
        assert f"{internal}  " not in out
        assert f"{internal}\n" not in out
