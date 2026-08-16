"""Nothing from the §6.10 rejection list is present in src/."""

from __future__ import annotations

from pathlib import Path

FORBIDDEN = (
    "user_agents.py",
    "tf-playwright-stealth",
    "tf_playwright_stealth",
    "playwright_stealth",
    "curl_cffi",
    "impersonate",
    "pick_ua",
    "UA_POOL",
    "ProxyPool",
    "JOBSCRAPER_PROXIES_FILE",
    "disable-blink-features=AutomationControlled",
    "human_pause",
    "NormalizedJob",
)


def test_rejected_donor_mechanisms_absent() -> None:
    root = Path("src")
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".md", ".json", ".txt", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN:
            if needle in text:
                # Provenance files may name the rejected symbols as exclusions.
                if (
                    "REJECT" in text
                    or "rejected" in text
                    or "§6.10" in text
                    or "EXCLUSIONS" in text
                ):  # noqa: E501
                    continue
                hits.append(f"{path}: {needle}")
    assert hits == [], "rejected donor mechanisms leaked into src:\n" + "\n".join(hits)
