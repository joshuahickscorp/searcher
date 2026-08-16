"""Frozen Job Scraper snapshot coordinates. No donor import."""

from __future__ import annotations

import os
from pathlib import Path

# Provenance only. The snapshot is not vendored; override if you hold a copy.
FROZEN_PATH = Path(os.environ.get("SEARCHER_JOBSCRAPER_FROZEN_DIR", "<jobscraper-frozen-dir>"))
MANIFEST_DIGEST = "3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2"
FREEZE_DATE = "2026-08-16"
EXCLUSIONS = (
    "scraper/user_agents.py",
    "scraper/browser.py",
    "tf-playwright-stealth",
    "playwright_stealth",
    "curl_cffi",
    "ProxyPool",
    "JOBSCRAPER_PROXIES_FILE",
    "--disable-blink-features=AutomationControlled",
    "data/profiles",
    "human_pause",
    "filters.py",
    "role_keywords.py",
    "fit_score",
    "NormalizedJob",
)
