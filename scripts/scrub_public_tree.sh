#!/usr/bin/env bash
# Public-tree scrub — Bible §36.3.
#
# Scans the working tree (tracked + untracked, not gitignored) and
# `git log -p` for private paths, personal identifiers, secrets, donor
# checkouts, caches, model weights, and identifying image metadata.
#
# Exit 0 if the working tree is clean. Prints file:line for every tree
# finding. History is always scanned and printed; leftover history is
# the supervising engineer's rewrite call, so it does not fail the tree
# gate unless SEARCHER_SCRUB_FAIL_ON_HISTORY=1.
#
# Re-runnable. Add a finding to the allowlist only with a comment that
# says why that exact string is safe. Never a blanket ignore.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export SEARCHER_SCRUB_FAIL_ON_HISTORY="${SEARCHER_SCRUB_FAIL_ON_HISTORY:-0}"

exec python3 - "$@" <<'PY'
from __future__ import annotations

import os
import re
import stat
import struct
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(os.environ.get("PWD") or ".").resolve()
FAIL_ON_HISTORY = os.environ.get("SEARCHER_SCRUB_FAIL_ON_HISTORY", "0") == "1"

# ---------------------------------------------------------------------------
# Allowlist. Each entry is an exact substring. Neutralized before matching.
# Keep this list small. A new exception needs a reason, not a glob.
# ---------------------------------------------------------------------------
ALLOWLIST: list[tuple[str, str]] = [
    # Honest User-Agent contact. Placeholder local-part, reserved TLD.
    (
        "operators@searcher.invalid",
        "documented UA contact; reserved .invalid TLD, not a mailbox",
    ),
    # Same UA, the public project URL it points at. Not a private host.
    (
        "https://github.com/searcher-project/searcher",
        "documented UA project URL",
    ),
    # Public VisionMCP donor remotes. Provenance, not a personal inbox.
    (
        "git@github.com:joshuahickscorp/visionmcp.git",
        "public VisionMCP donor SSH remote",
    ),
    (
        "https://github.com/joshuahickscorp/visionmcp",
        "public VisionMCP donor HTTPS remote",
    ),
    (
        "github.com/joshuahickscorp/visionmcp",
        "public VisionMCP donor host/path",
    ),
    # Documented local API / Pages-to-localhost configuration.
    (
        "http://127.0.0.1:8765",
        "documented local Searcher API base",
    ),
    (
        "http://localhost:8765",
        "documented local Searcher API base",
    ),
    (
        "http://127.0.0.1:8080",
        "documented local static UI when split from the API",
    ),
    (
        "http://localhost:8080",
        "documented local static UI when split from the API",
    ),
    (
        "http://127.0.0.1:8000",
        "documented alternate local static origin (CORS default)",
    ),
    (
        "http://localhost:8000",
        "documented alternate local static origin (CORS default)",
    ),
    (
        "http://127.0.0.1:8888",
        "documented local SearxNG from scripts/docker-compose.searx.yml",
    ),
    (
        "http://localhost:8888",
        "documented local SearxNG from scripts/docker-compose.searx.yml",
    ),
    # Portable donor default in scripts/setup_donor.sh. Not a baked home.
    (
        "${SEARCHER_DONOR_DIR:-$HOME/.searcher-donors/visionmcp}",
        "portable runtime default; operator overrides with SEARCHER_DONOR_DIR",
    ),
    (
        "$HOME/.searcher-donors/visionmcp",
        "same portable default, mentioned in setup_donor.sh comments",
    ),
    # Hostile fixture, not a real path. The index must refuse a candidate that
    # carries a filesystem path, so the fixture has to look like one.
    (
        "/home/someone/secret.png",
        "tests/unit/test_index.py: synthetic private path the index must reject",
    ),
]

# Localhost / RFC1918 / blocked-host names are legitimate in these paths
# because they are bind addresses, SSRF fixtures, or donor-dashboard notes.
# This is a localhost-category allowlist only — home paths still fail here.
LOCALHOST_PATH_ALLOW: list[tuple[str, str]] = [
    ("tests/", "SSRF and API tests of blocked destinations"),
    ("src/searcher/security/", "SSRF blocklist implementation"),
    ("src/searcher/core/config.py", "default bind and CORS localhost origins"),
    ("src/searcher/ranking/vetoes.py", "malicious-URL detector includes loopback"),
    ("src/searcher/sources/adapters/searx.py", "self-hosted SearxNG domain=localhost"),
    ("scripts/", "local API / SearxNG launchers"),
    ("web/", "documented local UI and stub API"),
    ("docs/architecture/API.md", "documents the local API bind"),
    ("docs/SEARCHER_FULL_IMPLEMENTATION_BIBLE.md", "policy: block localhost"),
    ("docs/audit/JOB_SCRAPER_CAPABILITY_HARVEST.md", "records donor loopback dashboard"),
    ("artifacts/audit/jobscraper-reuse-ledger.json", "records donor loopback dashboard"),
    ("README.md", "documents the localhost API"),
    ("LIMITATIONS.md", "states there is no hosted API"),
    ("PRIVACY.md", "local-by-default wording"),
    ("SECURITY.md", "threat model names localhost as blocked"),
    ("ARCHITECTURE.md", "local process graph"),
    ("CLAIMS.md", "localhost API claim evidence"),
    ("THIRD_PARTY_NOTICES.md", "no hosted service claim"),
    ("LICENSE", "license text"),
    ("docs/OPERATING.md", "operator manual: the whole point is telling you which local URL to open"),
    ("docs/architecture/SERVING.md", "documents the local bind and why the published page cannot call it"),
    ("artifacts/operator/", "captured transcript of a real clean-clone run against a local API"),
    ("artifacts/ui/", "captured browser verification against the local API"),
    ("artifacts/searcher-adversarial-recall.receipt.json", "records which local API the measurements came from"),
    ("artifacts/grading-round2/", "captured transcripts of an independent grading pass, quoting its own scan output"),
]

SKIP_TEXT_SCAN = {
    # The grading reports quote the scrub's findings, pattern names included.
    "docs/grading/ROUND_2.md",
    # The red-team report quotes the scrub's own findings verbatim, including
    # the literal pattern names. Rewriting them would edit the evidence.
    "docs/audit/REDTEAM_COMPLETENESS.md",
    # A transcript of this scan necessarily contains the patterns it scanned
    # for. Scrubbing them would falsify the evidence of the run.
    "artifacts/grading-round2/scrub.full.txt",
    "artifacts/grading-round2/scrub.log",
    "uv.lock",  # generated hash lockfile
    "scripts/scrub_public_tree.sh",  # this scanner's own pattern source
    # Standing authority. Its wording — including `$HOME/Downloads` as a
    # search-root instruction and the §36.3 "hidden benchmarks" list — is
    # part of the record and must not be rewritten to make the gate pass.
    "docs/SEARCHER_FULL_IMPLEMENTATION_BIBLE.md",
}

# Owner username split so this file does not itself contain the token.
OWNER_USERNAMES = ("scammer" + "mike",)

HOME_PATH = re.compile(
    r"(?:/Users|/home)/[A-Za-z0-9._-]+|(?:[A-Za-z]:\\Users\\)[A-Za-z0-9._-]+"
)
TILDE_HOME = re.compile(r"(?:(?<=\s)|(?<=`)|(?<=\()|(?<=')|(?<=\")|(?<=^))~(?:/|$)")
DOLLAR_HOME = re.compile(r"\$HOME\b")
EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |ENCRYPTED )?PRIVATE KEY-----"
)
TOKEN = re.compile(
    r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})\b"
)
SECRET_ASSIGN = re.compile(
    r"""(?:^|[\s,;])([A-Z][A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|API_KEY)[A-Z0-9_]*)\s*=\s*['\"][^'\"]{8,}"""
)
LOCALHOST_URL = re.compile(
    r"""(?:https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])\b"""
    r"""|(?:^|[\s'\"`=(])(?:localhost|127\.0\.0\.1)\b"""
    r"""|(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3})"""
    r"""|(?:192\.168\.\d{1,3}\.\d{1,3})"""
    r"""|(?:172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}))"""
)
# Hostnames only. Do not match Python attributes such as `decision.internal`.
INTERNAL_HOST = re.compile(
    r"(?:https?://[A-Za-z0-9.-]+\.(?:internal|corp|lan)\b|"
    r"\bmetadata\.google\.internal\b|\bmetadata\.goog\b)"
)
HIDDEN_BENCHMARK_FILE = re.compile(
    r"(?:hidden[-_]?benchmark|benchmark[-_]?answers?|benchmark[-_]?gold|gold[-_]?labels?)",
    re.I,
)
USER_IMAGE_NAME = re.compile(
    r"(?:IMG_\d{4,}|WhatsApp Image|DCIM|iPhone \d|Screenshot \d{4})",
    re.I,
)
ENV_NAME = re.compile(r"(?:^|/)\.env(?:\.|$)")

FORBIDDEN_TRACKED = (
    re.compile(r"(?:^|/)\.venv/"),
    re.compile(r"(?:^|/)node_modules/"),
    re.compile(r"(?:^|/)\.searcher-donors/"),
    re.compile(r"(?:^|/)\.pytest_cache/"),
    re.compile(r"(?:^|/)\.mypy_cache/"),
    re.compile(r"(?:^|/)\.ruff_cache/"),
    re.compile(r"(?:^|/)\.hypothesis/"),
    re.compile(r"(?:^|/)__pycache__/"),
    re.compile(r"(?:^|/)playwright-profile/"),
    re.compile(r"(?:^|/)\.browser-profile/"),
)
WEIGHT_EXT = {".pt", ".pth", ".onnx", ".safetensors", ".ckpt", ".gguf", ".h5"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff"}
LARGE_BYTES = 5 * 1024 * 1024

Finding = tuple[str, str, str, str]  # category, where, line_or_dash, detail


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def neutralize(text: str) -> str:
    for token, _reason in ALLOWLIST:
        if token in text:
            text = text.replace(token, " " * len(token))
    return text


def localhost_allowed(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    for prefix, _reason in LOCALHOST_PATH_ALLOW:
        if rel == prefix.rstrip("/") or rel.startswith(prefix):
            return True
    return False


def is_binary(data: bytes) -> bool:
    return b"\x00" in data[:8192]


def scan_line(rel: str, lineno: int, raw: str, into: list[Finding]) -> None:
    line = neutralize(raw.rstrip("\n"))
    where = f"{rel}:{lineno}"

    for match in HOME_PATH.finditer(line):
        into.append(("home_path", where, raw.strip(), "home-directory path"))

    for name in OWNER_USERNAMES:
        if name in line:
            into.append(("username", where, raw.strip(), "personal username"))

    if DOLLAR_HOME.search(line):
        into.append(("$HOME", where, raw.strip(), "$HOME expansion in committed text"))
    if TILDE_HOME.search(line):
        into.append(("tilde_home", where, raw.strip(), "tilde home path"))

    for match in EMAIL.finditer(line):
        addr = match.group(0)
        lower = addr.lower()
        if lower.startswith("git@github.com"):
            continue
        if lower.endswith(".invalid") or lower.endswith("@example.com"):
            continue
        into.append(("email", where, "<redacted personal email>", "personal email address"))

    if PRIVATE_KEY.search(line):
        into.append(("secret", where, "<redacted private key header>", "private key material"))
    if TOKEN.search(line):
        into.append(("secret", where, "<redacted token>", "token/key pattern"))
    if SECRET_ASSIGN.search(line):
        into.append(("secret", where, "<redacted assignment>", "secret-like assignment"))

    if not localhost_allowed(rel):
        if LOCALHOST_URL.search(line):
            into.append(
                (
                    "localhost",
                    where,
                    raw.strip()[:160],
                    "localhost/private address not on the documentation allowlist",
                )
            )
        if INTERNAL_HOST.search(line):
            into.append(("internal_host", where, raw.strip()[:160], "internal hostname"))


def png_text_chunks(data: bytes) -> list[tuple[str, bytes]]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return []
    pos = 8
    out: list[tuple[str, bytes]] = []
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        out.append((ctype.decode("latin1", "replace"), payload))
        if ctype == b"IEND":
            break
    return out


def image_identifying_metadata(path: Path, data: bytes) -> list[str]:
    hits: list[str] = []
    if data.startswith(b"\x89PNG"):
        for ctype, payload in png_text_chunks(data):
            if ctype == "eXIf":
                hits.append("PNG eXIf chunk")
                continue
            if ctype in {"tEXt", "iTXt", "zTXt"}:
                key = payload.split(b"\x00", 1)[0].decode("latin1", "replace")
                if key.lower() in {"software"} and b"PIL" in payload or b"Pillow" in payload:
                    continue
                if key.lower() in {"software", "comment"} and not any(
                    tok in payload.lower()
                    for tok in (b"/users/", b"/home/", b"@gmail", b"gps")
                ):
                    continue
                hits.append(f"PNG {ctype} {key}")
    elif data.startswith(b"\xff\xd8\xff"):
        if b"Exif\x00\x00" in data[:65536]:
            # GPS IFD presence is identifying. Bare EXIF from a camera is too.
            if b"GPS" in data[:131072] or b"\x00\x19\x88" in data[:8192]:
                hits.append("JPEG EXIF GPS")
            else:
                # Software-only EXIF (Pillow) is not a personal leak.
                head = data[:4096].lower()
                if b"pillow" not in head and b"pil" not in head:
                    hits.append("JPEG EXIF")
    return hits


def collect_tree_files() -> list[str]:
    tracked = [p for p in git("ls-files").splitlines() if p]
    extra = [p for p in git("ls-files", "-o", "--exclude-standard").splitlines() if p]
    seen: set[str] = set()
    out: list[str] = []
    for item in tracked + extra:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def scan_tree() -> list[Finding]:
    findings: list[Finding] = []
    for rel in collect_tree_files():
        path = ROOT / rel
        if not path.is_file():
            continue
        posix = rel.replace("\\", "/")

        if ENV_NAME.search(posix):
            findings.append(("secret", posix, "-", "env file present (contents not read)"))
            continue

        for pat in FORBIDDEN_TRACKED:
            if pat.search(posix):
                findings.append(("forbidden_path", posix, "-", "tracked/present cache, venv, or donor checkout"))
                break

        suffix = path.suffix.lower()
        if suffix in WEIGHT_EXT:
            findings.append(("model_weight", posix, "-", f"model-weight extension {suffix}"))

        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > LARGE_BYTES and posix != "uv.lock":
            findings.append(("large_artifact", posix, "-", f"{size} bytes"))

        if USER_IMAGE_NAME.search(path.name):
            findings.append(("user_image", posix, "-", "filename looks like a personal camera/screenshot image"))

        if HIDDEN_BENCHMARK_FILE.search(path.name):
            findings.append(("hidden_benchmark", posix, "-", "filename looks like hidden benchmark answers"))

        if posix in SKIP_TEXT_SCAN:
            continue

        if suffix in IMAGE_EXT:
            data = path.read_bytes()
            for hit in image_identifying_metadata(path, data):
                findings.append(("image_metadata", posix, "-", hit))
            continue

        if size > LARGE_BYTES:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if is_binary(data):
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = data.decode("latin1")
            except UnicodeDecodeError:
                continue
        for i, line in enumerate(text.splitlines(), 1):
            scan_line(posix, i, line, findings)
    return findings


AUTHOR_LINE = re.compile(r"^(?:Author|Commit|Committer):")


def scan_history() -> list[Finding]:
    findings: list[Finding] = []
    try:
        log = git("log", "-p", "--format=COMMIT %H %s")
    except subprocess.CalledProcessError as exc:
        findings.append(("history_error", "-", "-", str(exc)))
        return findings
    commit = "UNKNOWN"
    current_file = "?"
    for raw in log.splitlines():
        if raw.startswith("COMMIT "):
            commit = raw[7:47]
            continue
        if AUTHOR_LINE.match(raw):
            continue
        if raw.startswith("diff --git "):
            parts = raw.split(" b/", 1)
            current_file = parts[1] if len(parts) == 2 else "?"
            continue
        if raw.startswith("+++ ") or raw.startswith("--- "):
            continue
        if raw.startswith("+") or raw.startswith("-"):
            body = raw[1:]
            neutralized = neutralize(body)
            loc = f"{commit}:{current_file}"
            if HOME_PATH.search(neutralized):
                findings.append(("home_path", loc, "-", "home-directory path in history"))
            for name in OWNER_USERNAMES:
                if name in neutralized:
                    findings.append(("username", loc, "-", "personal username in history"))
            if DOLLAR_HOME.search(neutralized) or TILDE_HOME.search(neutralized):
                findings.append(("$HOME", loc, "-", "$HOME / tilde expansion in history"))
            for match in EMAIL.finditer(neutralized):
                addr = match.group(0).lower()
                if addr.startswith("git@github.com"):
                    continue
                if addr.endswith(".invalid") or addr.endswith("@example.com"):
                    continue
                findings.append(("email", loc, "-", "personal email in history (payload, not commit header)"))
            if PRIVATE_KEY.search(neutralized) or TOKEN.search(neutralized):
                findings.append(("secret", loc, "-", "secret-like material in history"))
    return findings


def print_group(title: str, findings: list[Finding]) -> None:
    print(title)
    if not findings:
        print("  (none)")
        print()
        return
    counts: Counter[str] = Counter(item[0] for item in findings)
    print("  counts:")
    for key, n in sorted(counts.items()):
        print(f"    {key}: {n}")
    print("  findings:")
    # Dedup identical (category, where, detail) while keeping order.
    seen: set[tuple[str, str, str]] = set()
    for category, where, snippet, detail in findings:
        key = (category, where, detail)
        if key in seen:
            continue
        seen.add(key)
        extra = f"  {snippet}" if snippet and snippet != "-" else ""
        print(f"    {where}  [{category}] {detail}{extra}")
    print()


def main() -> int:
    tree = scan_tree()
    history = scan_history()
    print("SEARCHER public-tree scrub (Bible §36.3)")
    print(f"root: {ROOT}")
    print()
    print_group("WORKING TREE", tree)
    print_group("GIT HISTORY (not rewritten by this script)", history)
    if history:
        print(
            "History findings are reported only. A history rewrite is the "
            "supervising engineer's call. Set SEARCHER_SCRUB_FAIL_ON_HISTORY=1 "
            "to make leftover history fail the gate after that rewrite."
        )
        print()
    if tree:
        print(f"FAIL: {len(tree)} working-tree finding(s)")
        return 1
    if FAIL_ON_HISTORY and history:
        print(f"FAIL: working tree clean, {len(history)} history finding(s)")
        return 1
    print("PASS: working tree is clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY
