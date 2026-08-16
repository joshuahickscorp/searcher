#!/usr/bin/env python3
"""Operator-only: fetch torchvision ResNet50 IMAGENET1K_V2 and write local weights.

A search never calls this. Weights land at $SEARCHER_DATA_ROOT/models/embedding.pt
(or --output). The file is a raw state_dict; identity is written beside it as
embedding.pt.json so the capability probe can stay torch-free.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


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
        from torchvision.models import ResNet50_Weights, resnet50
    except ImportError:
        print(
            "torch and torchvision are required. Install with: uv sync --extra vision",
            file=sys.stderr,
        )
        return 2

    weights = ResNet50_Weights.IMAGENET1K_V2
    model = resnet50(weights=weights)
    torch.save(model.state_dict(), dest)
    meta = {
        "identity": "torchvision.resnet50.IMAGENET1K_V2",
        "feature_dim": 2048,
        "resize": 256,
        "crop": 224,
        "mean": [0.485, 0.456, 0.406],
        "std": [0.229, 0.224, 0.225],
        "weights_enum": "IMAGENET1K_V2",
        "path": str(dest),
        "bytes": dest.stat().st_size,
    }
    dest.with_name(dest.name + ".json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")
    print(f"wrote {dest.name}.json identity={meta['identity']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
