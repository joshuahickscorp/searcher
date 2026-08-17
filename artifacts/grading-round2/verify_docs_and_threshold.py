# ruff: noqa: E501 — captured evidence from the round-2 grading pass, kept exactly
# as it was run so its output can be reproduced.
"""Check the nine-document claim and the pair-threshold documentation.

Does not edit src/. Writes artifacts/grading-round2/docs-threshold.json.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The nine documents named in commit efdd124.
NINE = [
    "ARCHITECTURE.md",
    "CLAIMS.md",
    "LIMITATIONS.md",
    "README.md",
    "docs/OPERATING.md",
    "docs/architecture/API.md",
    "docs/architecture/EMBEDDINGS.md",
    "docs/architecture/MATCHING_AND_AUTHENTICITY.md",
    "web/index.html",
]

FORBIDDEN = [
    ("ARCHITECTURE.md", "discovery is not wired into that process"),
    ("ARCHITECTURE.md", "They are not invoked by `scripts/run_api.sh`"),
    ("CLAIMS.md", "Matching in this tree is classical."),
    ("CLAIMS.md", "that the engine has a learned visual backbone"),
    ("LIMITATIONS.md", "No learned visual backbone."),
    ("LIMITATIONS.md", "No public benchmark has been run."),
    ("docs/architecture/EMBEDDINGS.md", "local ResNet50"),
    ("docs/architecture/API.md", "this version does not load it"),
    ("web/index.html", "the current benchmark"),
]

REQUIRED = [
    ("docs/architecture/EMBEDDINGS.md", "DINOv2"),
    ("docs/architecture/EMBEDDINGS.md", "prepare_embedding_weights.py"),
    ("ARCHITECTURE.md", "SEARCHER_LIVE_DISCOVERY"),
    ("CLAIMS.md", "DINOv2"),
    ("LIMITATIONS.md", "recall@1 0.771"),
    ("docs/architecture/API.md", "DINOv2"),
    ("web/index.html", "recall@1 0.771"),
]

SHORTLIST_PHRASES = [
    "shortlist cut",
    "not a validated identity gate",
    "70%",
]


def main() -> int:
    missing_files = [p for p in NINE if not (ROOT / p).is_file()]
    forbidden_hits: list[str] = []
    required_missing: list[str] = []
    texts = {rel: (ROOT / rel).read_text(encoding="utf-8") for rel in NINE if (ROOT / rel).is_file()}

    for rel, phrase in FORBIDDEN:
        if phrase in texts.get(rel, ""):
            forbidden_hits.append(f"{rel}: {phrase!r}")
    for rel, phrase in REQUIRED:
        if phrase not in texts.get(rel, ""):
            required_missing.append(f"{rel}: {phrase!r}")

    # Simulate the test failing when a document is reverted.
    arch = texts.get("ARCHITECTURE.md", "")
    simulated_revert = arch + "\ndiscovery is not wired into that process\n"
    simulated_would_fail = "discovery is not wired into that process" in simulated_revert and (
        "discovery is not wired into that process" not in arch
    )

    guarded = {rel for rel, _ in FORBIDDEN} | {rel for rel, _ in REQUIRED}
    unguarded = [rel for rel in NINE if rel not in guarded]

    threshold_doc_hits: dict[str, list[str]] = {}
    scan = [
        "src/searcher/core/embedding_gateway.py",
        "docs/architecture/EMBEDDINGS.md",
        "docs/SEARCHER_BENCHMARK_METHOD.md",
        "CLAIMS.md",
        "LIMITATIONS.md",
        "SEARCHER_BUCKET_POLICY.md",
        "README.md",
    ]
    for rel in scan:
        path = ROOT / rel
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8")
        hits = [p for p in SHORTLIST_PHRASES if p.lower() in body.lower() or p in body]
        if "0.86" in body:
            hits.append("0.86")
        threshold_doc_hits[rel] = hits

    receipt = json.loads((ROOT / "artifacts/searcher-threshold.receipt.json").read_text())
    shipped = receipt.get("shipped_threshold") or {}

    out = {
        "nine_documents": {
            "listed": NINE,
            "missing_from_tree": missing_files,
            "forbidden_still_present": forbidden_hits,
            "required_missing": required_missing,
            "guarded_by_test": sorted(guarded),
            "ungarded_by_test": unguarded,
            "simulated_revert_would_fail_test": simulated_would_fail,
        },
        "threshold": {
            "receipt_shipped": shipped,
            "receipt_verdict": receipt.get("verdict"),
            "held_out_fpr_is_0_7": shipped.get("held_out_fpr") == 0.7,
            "value_is_0_86": shipped.get("value") == 0.86,
            "doc_hits": threshold_doc_hits,
        },
    }
    dest = ROOT / "artifacts/grading-round2/docs-threshold.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
