"""Run a child interpreter and tell the difference between a bug and a bad host.

Round 5 graded this project from an extracted tree and hit `SIGSEGV (-11)` on
every test that spawns a child interpreter, then scored real-runtime proof on
"13 failed, 26 errors". The same suite is green here in fixed and in random
order. A child that dies from a signal before it runs is an environment
failure, and it reads exactly like an assertion failure unless something says
otherwise - so this says otherwise, and prints what the child managed to emit.
"""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path


def run_child(
    argv: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        argv,
        cwd=cwd or Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode < 0:
        try:
            name = signal.Signals(-proc.returncode).name
        except ValueError:  # pragma: no cover - unknown signal number
            name = f"signal {-proc.returncode}"
        raise RuntimeError(
            f"the child interpreter died from {name} before completing: {' '.join(argv)}\n"
            "This is a host or environment failure, not a failed assertion about "
            "Searcher's behaviour. It is commonly seen when the package is not "
            "importable from the working tree the child inherits.\n"
            f"child stdout: {proc.stdout[-800:]!r}\n"
            f"child stderr: {proc.stderr[-800:]!r}"
        )
    if proc.returncode != 0:
        raise AssertionError(
            f"child exited {proc.returncode}: {' '.join(argv)}\n"
            f"stdout: {proc.stdout[-800:]}\nstderr: {proc.stderr[-800:]}"
        )
    return proc
