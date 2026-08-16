"""Drive the real UI against a live API and write acceptance screenshots."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "orchestration"
SAMPLE = ROOT / "fixtures" / "images"
FALLBACK = ROOT / "web" / "images" / "sample-upload.png"
API = os.environ.get("SEARCHER_PROOF_URL", "http://127.0.0.1:8765")


def _images() -> list[Path]:
    found = sorted(SAMPLE.glob("*.png"))[:3] if SAMPLE.is_dir() else []
    if found:
        return found
    return [FALLBACK]


def _ps_browsers() -> str:
    proc = subprocess.run(
        ["ps", "-ax", "-o", "pid=,command="],
        check=False,
        capture_output=True,
        text=True,
    )
    lines = [
        line
        for line in proc.stdout.splitlines()
        if any(token in line.lower() for token in ("chrom", "playwright", "headless_shell"))
    ]
    return "\n".join(lines) if lines else "(none)"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ps_before.txt").write_text(_ps_browsers() + "\n", encoding="utf-8")
    images = _images()
    console_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on(
            "console",
            lambda msg: (
                console_errors.append(f"{msg.type}: {msg.text}") if msg.type == "error" else None
            ),
        )
        page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))
        page.goto(API, wait_until="networkidle")
        page.set_input_files("#file-input", [str(path) for path in images])
        page.fill("#know", "Dior Homme Army Trainer 07")
        page.click("#search-button")
        page.wait_for_selector("#results:not([hidden])", timeout=15000)
        page.screenshot(path=str(OUT / "01_streaming.png"), full_page=True)
        page.wait_for_function(
            """() => {
              const note = document.getElementById("terminal-note");
              const status = document.getElementById("campaign-status");
              const a = (note && note.textContent) || "";
              const b = (status && status.textContent) || "";
              const text = a + b;
              return /COMPLETE|PARTIAL|BLOCKED|CANCELLED|FAILED/i.test(text);
            }""",
            timeout=200000,
        )
        page.screenshot(path=str(OUT / "02_terminal.png"), full_page=True)
        page.click("#tab-real")
        page.screenshot(path=str(OUT / "03_tab_real.png"), full_page=True)
        page.click("#tab-possible")
        page.screenshot(path=str(OUT / "04_tab_possible.png"), full_page=True)
        details = page.locator("details.why")
        if details.count() > 0:
            details.first.click()
            page.screenshot(path=str(OUT / "05_expanded_card.png"), full_page=True)
        compare = page.locator("button", has_text="Compare")
        if compare.count() > 0:
            compare.first.click()
            page.wait_for_selector("#compare[open], dialog#compare", timeout=5000)
            page.screenshot(path=str(OUT / "06_compare.png"), full_page=True)
            closer = page.locator("#compare-close")
            if closer.count():
                closer.click()
        if details.count() == 0:
            page.screenshot(path=str(OUT / "05_expanded_card.png"), full_page=True)
        if compare.count() == 0:
            page.screenshot(path=str(OUT / "06_compare.png"), full_page=True)
        (OUT / "console.json").write_text(json.dumps(console_errors, indent=2), encoding="utf-8")
        status = page.locator("#campaign-status").inner_text()
        terminal = page.locator("#terminal-note").inner_text()
        (OUT / "ui_status.txt").write_text(
            f"status={status}\nterminal={terminal}\n", encoding="utf-8"
        )
        browser.close()
    (OUT / "ps_after.txt").write_text(_ps_browsers() + "\n", encoding="utf-8")
    print("screenshots", OUT)
    print("console_errors", len(console_errors))
    for line in console_errors:
        print("CONSOLE", line)
    return 0 if not console_errors else 2


if __name__ == "__main__":
    sys.exit(main())
