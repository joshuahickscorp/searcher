# ruff: noqa: E501 — this is captured evidence, not shipped code: the long lines are
# embedded JavaScript and regexes that break if wrapped.
"""Drive the rebuilt Searcher UI and write acceptance evidence."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "ui"
IMAGES = [
    ROOT / "fixtures" / "images" / "trainer_a.png",
    ROOT / "fixtures" / "images" / "trainer_b.png",
    ROOT / "fixtures" / "images" / "trainer_c.png",
]
URL = "http://127.0.0.1:8766/"
STATIC = "http://127.0.0.1:8080/"


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def parse_multipart(raw: str | None) -> dict:
    fields: dict[str, list[str]] = {}
    if not raw:
        return fields
    names = re.findall(r'Content-Disposition: form-data; name="([^"]+)"(?:; filename="([^"]*)")?', raw)
    # Split on boundary-ish disposition blocks and capture following text values.
    chunks = re.split(r"\r\n--[^\r\n]+", raw)
    for chunk in chunks:
        match = re.search(
            r'Content-Disposition: form-data; name="([^"]+)"(?:; filename="([^"]*)")?\r\n(?:Content-Type: [^\r\n]+\r\n)?\r\n(.*)$',
            chunk,
            re.S,
        )
        if not match:
            continue
        name, filename, value = match.group(1), match.group(2), match.group(3)
        if filename is not None:
            fields.setdefault(name, []).append(f"<file {filename} {len(value)} bytes>")
        else:
            fields.setdefault(name, []).append(value.rstrip("\r\n"))
    if not fields and names:
        fields["_names_only"] = [n[0] for n in names]
    return fields


def attach_via_drop(page, path: Path) -> None:
    page.evaluate(
        """({payload, name}) => {
          const bytes = Uint8Array.from(atob(payload), (c) => c.charCodeAt(0));
          const file = new File([bytes], name, { type: "image/png" });
          const dt = new DataTransfer();
          dt.items.add(file);
          const zone = document.getElementById("dropzone");
          zone.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: dt }));
          zone.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));
        }""",
        {"payload": b64(path), "name": path.name},
    )


def attach_via_paste(page, path: Path) -> None:
    page.evaluate(
        """({payload, name}) => {
          const bytes = Uint8Array.from(atob(payload), (c) => c.charCodeAt(0));
          const file = new File([bytes], name, { type: "image/png" });
          const dt = new DataTransfer();
          dt.items.add(file);
          const ev = new Event("paste", { bubbles: true, cancelable: true });
          Object.defineProperty(ev, "clipboardData", { value: dt });
          document.dispatchEvent(ev);
        }""",
        {"payload": b64(path), "name": path.name},
    )


def first_screen_inventory(page) -> dict:
    viewport = page.viewport_size
    height = viewport["height"] if viewport else 0
    items = {}
    for selector in [
        "#home-link",
        "#source-scopes",
        "#dropzone",
        "#item-name",
        "#know",
        "#tag-input",
        "#search-button",
        "#recent-wrap",
        ".site-footer",
        ".tagline",
        "#api-banner",
    ]:
        loc = page.locator(selector)
        if loc.count() == 0:
            items[selector] = "absent"
            continue
        box = loc.bounding_box()
        hidden = loc.is_hidden()
        if hidden or box is None:
            items[selector] = "hidden"
        else:
            items[selector] = {
                "y": round(box["y"], 1),
                "h": round(box["height"], 1),
                "in_fold": box["y"] < height,
            }
    return items


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"console": [], "errors": [], "checks": {}}
    posted: dict = {}

    def on_console(msg) -> None:
        line = f"{msg.type}: {msg.text}"
        report["console"].append(line)
        if msg.type == "error":
            report["errors"].append(line)

    def on_pageerror(exc) -> None:
        report["errors"].append(f"pageerror: {exc}")

    def on_request(request) -> None:
        if request.method == "POST" and request.url.rstrip("/").endswith("/v1/searches"):
            posted["url"] = request.url
            posted["post_data"] = request.post_data
            posted["fields"] = parse_multipart(request.post_data)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        # --- first screen: dark default, light preference, both viewports ---
        shots = [
            ("after-desktop-dark-1280x800", 1280, 800, "no-preference"),
            ("after-phone-dark-390x844", 390, 844, "no-preference"),
            ("after-desktop-light-1280x800", 1280, 800, "light"),
            ("after-phone-light-390x844", 390, 844, "light"),
            ("after-desktop-dark-pref-1280x800", 1280, 800, "dark"),
        ]
        for name, w, h, scheme in shots:
            context = browser.new_context(
                viewport={"width": w, "height": h},
                color_scheme=scheme,
            )
            page = context.new_page()
            page.on("console", on_console)
            page.on("pageerror", on_pageerror)
            page.goto(URL, wait_until="networkidle")
            page.wait_for_selector("#search-form")
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
            report["checks"][name] = {
                "scheme": scheme,
                "bg": page.evaluate("getComputedStyle(document.body).backgroundColor"),
                "fg": page.evaluate("getComputedStyle(document.body).color"),
                "inventory": first_screen_inventory(page),
                "url": page.url,
                "legitimate": page.locator("#scope-legitimate").is_checked(),
                "replica": page.locator("#scope-replica").is_checked(),
            }
            context.close()

        # --- unavailable state on the static origin with no API ---
        context = browser.new_context(viewport={"width": 1280, "height": 800}, color_scheme="dark")
        page = context.new_page()
        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.goto(STATIC, wait_until="networkidle")
        page.wait_for_selector("#api-banner")
        page.screenshot(path=str(OUT / "after-api-unavailable.png"), full_page=False)
        report["checks"]["unavailable"] = {
            "banner": page.locator("#api-banner").inner_text(),
            "hidden": page.locator("#api-banner").is_hidden(),
        }
        context.close()

        # --- live form + search ---
        context = browser.new_context(viewport={"width": 1280, "height": 800}, color_scheme="dark")
        page = context.new_page()
        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("request", on_request)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_selector("#search-form")

        # Attach three images by three methods.
        attach_via_drop(page, IMAGES[0])
        page.wait_for_function("document.querySelectorAll('#thumbs .thumb').length === 1")
        page.set_input_files("#file-input", str(IMAGES[1]))
        page.wait_for_function("document.querySelectorAll('#thumbs .thumb').length === 2")
        attach_via_paste(page, IMAGES[2])
        page.wait_for_function("document.querySelectorAll('#thumbs .thumb').length === 3")
        page.screenshot(path=str(OUT / "after-images-attached.png"), full_page=False)
        report["checks"]["images"] = page.locator("#thumbs .thumb").count()

        page.fill("#item-name", "Dior Homme Army Trainer")
        page.fill("#know", "black leather, 2007, size 42")
        page.fill("#tag-input", "dior")
        page.keyboard.press("Enter")
        page.fill("#tag-input", "trainer")
        page.keyboard.press("Enter")

        # Toggle both scopes on (legitimate already on).
        if not page.locator("#scope-legitimate").is_checked():
            page.locator("#scope-legitimate").check()
        if not page.locator("#scope-replica").is_checked():
            page.locator("#scope-replica").check()
        page.locator("#source-scopes").hover()
        page.screenshot(path=str(OUT / "after-form-filled-scopes.png"), full_page=False)
        report["checks"]["url_after_toggle"] = page.url
        report["checks"]["scopes_checked"] = {
            "legitimate": page.locator("#scope-legitimate").is_checked(),
            "replica": page.locator("#scope-replica").is_checked(),
        }

        # Keyboard-only pass: tab through the form and confirm focus.
        page.locator("#home-link").focus()
        focused = []
        for _ in range(12):
            page.keyboard.press("Tab")
            focused.append(
                page.evaluate(
                    """() => {
                      const el = document.activeElement;
                      return el ? (el.id || el.tagName + '.' + el.className) : null;
                    }"""
                )
            )
        report["checks"]["keyboard_tab_order"] = focused
        page.screenshot(path=str(OUT / "after-keyboard-pass.png"), full_page=False)

        page.click("#search-button")
        page.wait_for_selector("#results:not([hidden])", timeout=15000)
        page.screenshot(path=str(OUT / "after-search-streaming.png"), full_page=False)

        page.wait_for_function(
            """() => {
              const note = document.getElementById("terminal-note");
              const status = document.getElementById("campaign-status");
              const text = ((note && note.textContent) || "") + " " + ((status && status.textContent) || "");
              return /COMPLETE|PARTIAL|BLOCKED|CANCELLED|FAILED/i.test(text);
            }""",
            timeout=180000,
        )
        page.screenshot(path=str(OUT / "after-search-terminal.png"), full_page=True)
        report["checks"]["terminal_status"] = page.locator("#campaign-status").inner_text()
        report["checks"]["terminal_note"] = page.locator("#terminal-note").inner_text()
        report["checks"]["coverage_visible"] = page.locator("#coverage").is_visible()
        report["checks"]["coverage_text"] = page.locator("#coverage").inner_text() if page.locator("#coverage").is_visible() else ""
        report["checks"]["empty_real_visible"] = page.locator("#empty-real").is_visible()
        report["checks"]["empty_real_text"] = page.locator("#empty-real").inner_text() if page.locator("#empty-real").is_visible() else ""
        report["checks"]["replica_tab_hidden"] = page.locator("#tab-replica").is_hidden()
        report["checks"]["disclaimer"] = page.locator("#disclaimer").inner_text()

        # Persist scopes across reload.
        url_before_reload = page.url
        page.reload(wait_until="networkidle")
        report["checks"]["url_after_reload"] = page.url
        report["checks"]["scopes_after_reload"] = {
            "legitimate": page.locator("#scope-legitimate").is_checked(),
            "replica": page.locator("#scope-replica").is_checked(),
        }
        page.screenshot(path=str(OUT / "after-reload-scopes.png"), full_page=False)

        # Shared-link scopes: replica only.
        page.goto(URL + "?scopes=replica", wait_until="networkidle")
        report["checks"]["shared_link"] = {
            "url": page.url,
            "legitimate": page.locator("#scope-legitimate").is_checked(),
            "replica": page.locator("#scope-replica").is_checked(),
        }
        page.screenshot(path=str(OUT / "after-shared-link-replica.png"), full_page=False)

        # Routes still work.
        page.goto(URL + "#/limitations", wait_until="networkidle")
        report["checks"]["limitations"] = {
            "visible": page.locator("#view-limitations").is_visible(),
            "text": page.locator("#view-limitations h1").inner_text(),
        }
        page.screenshot(path=str(OUT / "after-limitations.png"), full_page=False)
        page.goto(URL + "#/privacy", wait_until="networkidle")
        report["checks"]["privacy"] = {
            "visible": page.locator("#view-privacy").is_visible(),
            "text": page.locator("#view-privacy h1").inner_text(),
        }
        page.screenshot(path=str(OUT / "after-privacy.png"), full_page=False)

        # Validation message still present.
        page.goto(URL, wait_until="networkidle")
        page.evaluate(
            """() => {
              const file = new File([new Uint8Array([1,2,3,4])], "notes.txt", { type: "text/plain" });
              const dt = new DataTransfer();
              dt.items.add(file);
              const ev = new Event("paste", { bubbles: true, cancelable: true });
              Object.defineProperty(ev, "clipboardData", { value: dt });
              document.dispatchEvent(ev);
            }"""
        )
        # paste handler filters by looksLikeImage, so a txt paste is ignored — use add via input instead
        bad = OUT / "_bad.txt"
        bad.write_text("not an image", encoding="utf-8")
        page.set_input_files("#file-input", str(bad))
        report["checks"]["validation"] = page.locator("#image-error").inner_text()
        page.screenshot(path=str(OUT / "after-validation.png"), full_page=False)

        context.close()
        browser.close()

    report["posted"] = {
        "url": posted.get("url"),
        "fields": posted.get("fields"),
    }
    if posted.get("post_data"):
        (OUT / "search-create-raw.txt").write_text(posted["post_data"], encoding="utf-8", errors="replace")
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT / "console.log").write_text("\n".join(report["console"]) + "\n", encoding="utf-8")
    print(json.dumps({
        "errors": report["errors"],
        "images": report["checks"].get("images"),
        "scopes": report["checks"].get("scopes_checked"),
        "after_reload": report["checks"].get("scopes_after_reload"),
        "shared": report["checks"].get("shared_link"),
        "terminal": report["checks"].get("terminal_status"),
        "coverage": report["checks"].get("coverage_visible"),
        "empty": report["checks"].get("empty_real_visible"),
        "posted_scopes": (posted.get("fields") or {}).get("source_scopes"),
        "posted_text": (posted.get("fields") or {}).get("text"),
        "validation": report["checks"].get("validation"),
        "keyboard": report["checks"].get("keyboard_tab_order"),
        "bg_dark": report["checks"].get("after-desktop-dark-1280x800", {}).get("bg"),
        "bg_light": report["checks"].get("after-desktop-light-1280x800", {}).get("bg"),
    }, indent=2))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
