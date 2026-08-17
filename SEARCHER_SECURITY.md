# Searcher security

Bible §39 name. Draws from `SECURITY.md` (Bible §29). This file is
the §39 binding. Threat-model list and control table stay in
`SECURITY.md`.

There is no hosted Searcher API. A process that binds the
documented local API origin (`http://127.0.0.1:8765`) is still a
network server on that machine.

## Controls implemented in this tree

| Control | Where | Evidence command |
|---|---|---|
| Scheme allowlist `http`/`https` only; block loopback, link-local, private, reserved, metadata hosts; redirects re-validated | `src/searcher/security/ssrf.py` | `uv run pytest -q tests/security/test_ssrf_matrix.py` |
| Upload magic-bytes, dimension and decompression caps, path-name refusal | `src/searcher/reference/validation.py` | `uv run pytest -q tests/unit/test_upload_validation.py` |
| EXIF orientation then strip; EXIF quarantined | `src/searcher/reference/imaging.py` | reference pipeline tests |
| Response size and decompression-ratio limits | `src/searcher/security/limits.py` | same security suite |
| Prompt-injection contract; listing and image text treated as data | `src/searcher/matching/adjudicator.py` | `uv run pytest -q tests/adversarial/test_prompt_injection_listing.py tests/adversarial/test_prompt_injection_image.py` |
| Cross-campaign isolation | `src/searcher/evidence/content_store.py` | `uv run pytest -q tests/property/test_p07_campaign_isolation.py` |
| API does not fetch a user-supplied URL | `src/searcher/api/` | `uv run pytest -q tests/security/test_api_security.py` |
| CORS never pairs credentials with `*` | `src/searcher/core/config.py` | `tests/security/test_api_security.py` |
| Honest User-Agent; no TLS impersonation, UA rotation, or stealth | Job Scraper §6.10 rejections | `uv run pytest -q tests/unit/test_donor_rejection.py` |
| Browser: fresh context, headless, downloads off, extensions off, reap on close | `src/searcher/sources/browser.py` | `uv run pytest -q tests/real_runtime/test_browser_leak.py` |

Loopback is allowed only when `SEARCHER_ALLOW_LOOPBACK=1`, which
tests set. Production must not set it.

Receipt of the security suite run at this binding:
`artifacts/searcher-security.receipt.json`.

## Not implemented, or only partial

- Full Bible §29.4 browser sandbox (no explicit deny for clipboard,
  geolocation, camera, microphone). JavaScript is enabled because
  listing pages need it.
- Authenticated marketplace adapters and a credential store.
- Hosted multi-tenant isolation. One process, one operator.
- Abuse quotas and public authentication. Out of scope until there
  is a hosted API. There is not one.
- History scrub is not clean. `./scripts/scrub_public_tree.sh`
  with `SEARCHER_SCRUB_FAIL_ON_HISTORY=1` fails on leftover home
  paths in git history (`docs/grading/ROUND_2.md`). The working-tree
  gate is a separate check.

## Secrets

Backend only. Environment. Never sent to the frontend, never
included in logs, redacted from receipts.

## What is not established

- A third-party penetration test.
- That soak and abuse tests exercise live discovery. They set
  `SEARCHER_LIVE_DISCOVERY=0` and assert `BLOCKED`
  (`docs/grading/ROUND_2.md`).
