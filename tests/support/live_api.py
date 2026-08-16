"""Start a loopback Searcher API process for abuse and soak tests."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def parse_sse(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in text.split("\n\n"):
        if not block.strip() or block.lstrip().startswith(":"):
            continue
        item: dict[str, Any] = {"id": None, "event": None, "data": {}}
        for line in block.splitlines():
            if line.startswith("id:"):
                item["id"] = int(line[3:].strip())
            elif line.startswith("event:"):
                item["event"] = line[6:].strip()
            elif line.startswith("data:"):
                raw = line[5:].strip() or "{}"
                item["data"] = json.loads(raw)
        if item["event"]:
            events.append(item)
    return events


@dataclass
class LiveApi:
    base: str
    data_root: Path
    pid: int
    process: subprocess.Popen[str]

    def client(self, timeout: float = 15.0) -> httpx.Client:
        # verify=False avoids loading certifi (sandbox cannot read the CA bundle).
        # The server is loopback HTTP, so there is no TLS to verify.
        return httpx.Client(base_url=self.base, timeout=timeout, verify=False)


@contextmanager
def live_api(
    data_root: Path,
    *,
    extra_env: dict[str, str] | None = None,
    ready_seconds: float = 20.0,
) -> Iterator[LiveApi]:
    """Spawn `searcher serve` on loopback. Never pointed at a remote host."""
    data_root.mkdir(parents=True, exist_ok=True)
    port = free_loopback_port()
    env = os.environ.copy()
    env.update(
        {
            "SEARCHER_DATA_ROOT": str(data_root),
            "SEARCHER_LIVE_DISCOVERY": "0",
            "SEARCHER_SERVE_WEB": "0",
            "SEARCHER_API_HOST": "127.0.0.1",
            "SEARCHER_API_PORT": str(port),
            "PYTHONUNBUFFERED": "1",
        }
    )
    if extra_env:
        env.update(extra_env)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "searcher",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-static",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + ready_seconds
    last_error = ""
    try:
        while time.time() < deadline:
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr else ""
                raise RuntimeError(f"API process exited {process.returncode}: {stderr}")
            try:
                response = httpx.get(f"{base}/v1/health", timeout=1.0, verify=False)
                if response.status_code == 200:
                    yield LiveApi(
                        base=base, data_root=data_root, pid=process.pid, process=process
                    )
                    return
                last_error = f"health {response.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
            time.sleep(0.05)
        raise TimeoutError(f"API did not become ready: {last_error}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def wait_terminal(client: httpx.Client, search_id: str, timeout: float = 45.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] | None = None
    while time.time() < deadline:
        response = client.get(f"/v1/searches/{search_id}")
        if response.status_code != 200:
            last = {"status_code": response.status_code, "body": response.text}
            time.sleep(0.05)
            continue
        last = response.json()
        if last.get("terminal_status"):
            return last
        time.sleep(0.05)
    raise AssertionError(f"campaign did not reach a terminal verdict: {last}")
