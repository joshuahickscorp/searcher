# Security

Bible §29. How to think about this engine, what the tree actually
implements, and how to report a problem.

There is no hosted Searcher API. A local process that binds
`127.0.0.1` is still a network server on that machine. Treat it as
one.

## Threat model (Bible §29.1)

Audit these classes. “In the model” is not the same as “handled.”

- malicious image metadata
- decompression bombs
- malformed images
- path traversal
- symlink escape
- arbitrary file read/write
- SSRF
- private-network access
- hostile redirects
- data URLs
- file URLs
- browser profile theft
- prompt injection in listing pages
- prompt injection rendered inside images
- malicious JavaScript
- endless pages
- archive bombs
- command injection
- secret leakage
- cross-search data leakage
- result tampering
- evaluator substitution
- malicious model files
- unbounded browser downloads
- denial of service

## Implemented in this tree

| Control | Where | Evidence |
|---|---|---|
| Scheme allowlist `http`/`https` only | `src/searcher/security/ssrf.py` | `tests/security/test_ssrf_matrix.py` |
| Block localhost, link-local, private, reserved, metadata hosts | same | same |
| Redirects re-validated every hop | `assert_redirect_safe` | `test_redirect_into_private_refused`, `test_redirect_revalidation_on_real_transport` |
| Upload magic-bytes, dimension and decompression caps, path-name refusal | `src/searcher/reference/validation.py` | `tests/unit/test_upload_validation.py` |
| EXIF orientation applied then metadata stripped; EXIF dumped to quarantine | `src/searcher/reference/imaging.py` | reference pipeline tests |
| Response size and decompression-ratio limits | `src/searcher/security/limits.py` | `test_response_size_limit`, `test_decompression_bomb_limit` |
| Prompt-injection contract attached; listing/image text treated as data | `src/searcher/reference/injection.py`, `src/searcher/matching/adjudicator.py` | `tests/adversarial/test_prompt_injection_listing.py`, `test_prompt_injection_image.py` |
| Cross-campaign isolation of private artifacts | `src/searcher/evidence/content_store.py` | `tests/property/test_p07_campaign_isolation.py` |
| API does not fetch a user-supplied URL | `docs/architecture/API.md`, `src/searcher/api/` | `tests/security/test_api_security.py` |
| CORS never pairs credentials with `*`; default origins are localhost | `src/searcher/core/config.py` | `test_api_security.py` |
| Structured logs omit uploads, filenames, secrets, listing bodies | `src/searcher/api/logging.py` | reviewed against the code |
| Honest User-Agent, no TLS impersonation, no UA rotation, no stealth | `HONEST_USER_AGENT`, Job Scraper §6.10 rejections | `tests/unit/test_donor_rejection.py` |
| Browser: fresh context, headless, downloads off, extensions off, reap on close | `src/searcher/sources/browser.py` | `tests/real_runtime/test_browser_leak.py` |

Network policy (Bible §29.2) is the allowlist above. Loopback is
allowed only when `SEARCHER_ALLOW_LOOPBACK=1`, which tests set.
Production must not set it.

## Not implemented, or only partially

- **Full §29.4 browser sandbox.** The pool does not set an explicit
  deny for clipboard, geolocation, camera, or microphone. It does not
  grant a filesystem. It does not load a personal profile or cookies.
  JavaScript is enabled (listing pages need it).
- **Authenticated marketplace adapters.** eBay and Etsy report
  `AUTH_REQUIRED` without an operator key. There is no encrypted
  credential store, no cookie export, no OAuth flow.
- **Hosted multi-tenant isolation.** One process, one operator. The
  campaign store isolates campaigns from each other; it is not a
  multi-user auth boundary.
- **Remote-model allowlist.** There is no third-party model upload
  path. If one is added, it needs its own review.
- **Secret store.** Secrets belong in the environment. They must not
  be committed, logged, or sent to the frontend.
- **Abuse quotas / public authentication.** Out of scope until there
  is a hosted API. There is not one.

## Secrets

Backend only. Environment or a secret store. Never sent to the
frontend, never included in logs, redacted from receipts, never
exposed to models unless an adapter requires it and policy permits it.

The honest User-Agent contact is `operators@searcher.invalid` (a
placeholder, reserved TLD).

## How to report a problem

Do not open a public issue that includes a secret, a user image, or a
working exploit.

Once the repository has a public GitHub remote, use GitHub's private
vulnerability reporting on that repository. Until then, contact the
copyright holder named in [LICENSE](LICENSE).

Include: Searcher version (`0.1.0` / `CODE_VERSION`), the commit SHA,
what you ran, and a minimal repro that does not contain other people's
data.

See also [PRIVACY.md](PRIVACY.md) and [LIMITATIONS.md](LIMITATIONS.md).
