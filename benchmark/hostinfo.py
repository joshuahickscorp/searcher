"""Host, code version, and git identity for receipts."""

from __future__ import annotations

import socket
import subprocess
from typing import Any

from searcher import CODE_VERSION, SCHEMA_VERSION
from searcher.core.policy import POLICY_VERSION
from searcher.core.time import format_utc, utc_now

from .paths import ROOT


def git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    sha = out.strip()
    return sha or "unknown"


def host_name() -> str:
    return socket.gethostname() or "unknown"


def run_identity() -> dict[str, Any]:
    return {
        "code_version": CODE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "git_sha": git_sha(),
        "host": host_name(),
        "measured_at": format_utc(utc_now()),
    }
