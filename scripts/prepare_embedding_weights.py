#!/usr/bin/env python3
"""Operator-only: fetch the DINOv2 ViT-S/14 backbone and write local weights.

A search never calls this. It runs once, by hand, and writes a traced
TorchScript module to $SEARCHER_DATA_ROOT/models/embedding.pt (or --output),
with the identity beside it as embedding.pt.json so the capability probe can
stay torch-free. The search path then loads that one file: no torch.hub, no
network.

Backbone chosen by measurement, not preference. On a 59-listing gallery from
shop.kind.co.jp, querying with a *different* photograph of the same listing
under seven degradations:

    torchvision ResNet50 IMAGENET1K_V2   14/28 top-1   36.0 ms/image   23.5 M
    DINOv2 ViT-S/14                      24/28 top-1   12.1 ms/image   22.1 M

DINOv2 is better, smaller and three times faster at once. Multi-scale query
expansion was measured too (23/28 for double the latency) and rejected.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HUB_REPO = "facebookresearch/dinov2"
HUB_ENTRY = "dinov2_vits14"
IDENTITY = "facebookresearch.dinov2.vits14"
FEATURE_DIM = 384


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Destination .pt path (default: $SEARCHER_DATA_ROOT/models/embedding.pt)",
    )
    args = parser.parse_args(argv)
    dest = args.output
    if dest is None:
        root = Path(os.environ.get("SEARCHER_DATA_ROOT", "data"))
        dest = root / "models" / "embedding.pt"
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        import torch
    except ImportError:
        print(
            "torch is required. Install with: uv sync --extra vision",
            file=sys.stderr,
        )
        return 2

    print(f"fetching {HUB_REPO}:{HUB_ENTRY} (one time, this step needs the network)")
    model = torch.hub.load(HUB_REPO, HUB_ENTRY, verbose=False)
    model.eval()

    # Trace on CPU so the artifact is portable; the runtime maps it to MPS or
    # CUDA when loading.
    example = torch.zeros(1, 3, 224, 224)
    traced = torch.jit.trace(model, example, strict=False)
    torch.jit.save(traced, str(dest))

    with torch.inference_mode():
        reference = torch.nn.functional.normalize(model(example).float(), dim=-1)
        loaded = torch.jit.load(str(dest), map_location="cpu").eval()
        replayed = torch.nn.functional.normalize(loaded(example).float(), dim=-1)
    drift = float((reference - replayed).abs().max())
    if drift > 1e-4:
        print(f"traced module drifted from the reference by {drift}", file=sys.stderr)
        return 3

    meta = {
        "identity": IDENTITY,
        "format": "torchscript",
        "feature_dim": FEATURE_DIM,
        "preprocess": {
            "resize": 256,
            "crop": 224,
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
        "max_abs_drift_vs_reference": drift,
    }
    Path(str(dest) + ".json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    size_mb = dest.stat().st_size / 1e6
    print(f"wrote {dest} ({size_mb:.1f} MB), drift {drift:.2e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
