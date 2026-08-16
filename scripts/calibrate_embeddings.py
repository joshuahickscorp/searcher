#!/usr/bin/env python3
"""Build the kind.co.jp calibration set and choose an embedding threshold.

Downloads live listing photos (admitted KIND product/collection URLs only),
resizes them into fixtures/, scores labelled pairs, and writes
artifacts/searcher-match-calibration.receipt.json.

Requires local weights (scripts/prepare_embedding_weights.py) and the vision extra.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from searcher.core.config import HONEST_USER_AGENT  # noqa: E402
from searcher.retrieval.embeddings import (  # noqa: E402
    BACKBONE_IDENTITY,
    OPERATING_THRESHOLD,
    TARGET_FPR,
    cosine_similarity,
    embed_png,
    resolve_backend,
)

TARGET_HANDLE = "8001001141404"
TARGET_URL = f"https://shop.kind.co.jp/products/{TARGET_HANDLE}"
VENDOR_JSON = "https://shop.kind.co.jp/collections/willy-chavarria/products.json?limit=250"
FETCH_DATE = datetime.now(UTC).date().isoformat()
MAX_BYTES = 200_000
MAX_IMAGES = 40


def _get(client: httpx.Client, url: str) -> bytes:
    response = client.get(url, headers={"User-Agent": HONEST_USER_AGENT}, timeout=30.0)
    response.raise_for_status()
    return response.content


def _shrink(data: bytes) -> bytes:
    image = Image.open(BytesIO(data)).convert("RGB")
    image.thumbnail((512, 512), Image.Resampling.BILINEAR)
    quality = 85
    out = BytesIO()
    image.save(out, format="JPEG", quality=quality, optimize=True)
    while out.tell() > MAX_BYTES and quality > 40:
        quality -= 10
        out = BytesIO()
        image.save(out, format="JPEG", quality=quality, optimize=True)
    if out.tell() > MAX_BYTES:
        image.thumbnail((384, 384), Image.Resampling.BILINEAR)
        out = BytesIO()
        image.save(out, format="JPEG", quality=70, optimize=True)
    return out.getvalue()


def _to_png(data: bytes) -> bytes:
    image = Image.open(BytesIO(data)).convert("RGB")
    buf = BytesIO()
    image.save(buf, format="PNG", optimize=True)
    if buf.tell() <= MAX_BYTES:
        return buf.getvalue()
    return data


def _pairs(n: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            out.append((i, j))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=ROOT / "fixtures" / "known_item_kind")
    parser.add_argument(
        "--receipt",
        type=Path,
        default=ROOT / "artifacts" / "searcher-match-calibration.receipt.json",
    )
    args = parser.parse_args(argv)

    backend = resolve_backend()
    if backend is None:
        print(
            "no local embedding weights; run scripts/prepare_embedding_weights.py", file=sys.stderr
        )
        return 2
    try:
        import torch
    except ImportError:
        print("torch is required for calibration", file=sys.stderr)
        return 2
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    os.environ.setdefault("SEARCHER_EMBEDDING_DEVICE", device)

    images_dir = args.fixtures / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(follow_redirects=True) as client:
        catalog = json.loads(_get(client, VENDOR_JSON))
        products = [p for p in catalog.get("products") or [] if isinstance(p, dict)]
        target = next((p for p in products if p.get("handle") == TARGET_HANDLE), None)
        if target is None:
            print(f"target {TARGET_HANDLE} missing from vendor catalog", file=sys.stderr)
            return 1
        same_type = [
            p
            for p in products
            if str(p.get("product_type") or "") == str(target.get("product_type") or "")
            and p.get("handle") != TARGET_HANDLE
        ]
        chosen = [target] + same_type[:9]
        if len(chosen) < 10:
            extras = [p for p in products if p.get("handle") != TARGET_HANDLE and p not in chosen]
            chosen.extend(extras[: 10 - len(chosen)])

        records: list[dict[str, Any]] = []
        saved = 0
        for product in chosen:
            handle = str(product.get("handle"))
            srcs = [str(img["src"]) for img in (product.get("images") or []) if img.get("src")][:3]
            local_names: list[str] = []
            for index, src in enumerate(srcs, start=1):
                if saved >= MAX_IMAGES:
                    break
                raw = _get(client, src)
                jpeg = _shrink(raw)
                png = _to_png(jpeg)
                if len(png) > MAX_BYTES:
                    png = jpeg
                name = (
                    f"{handle}_{index}.jpg" if png[:2] == b"\xff\xd8" else f"{handle}_{index}.png"
                )
                (images_dir / name).write_bytes(png)
                local_names.append(name)
                saved += 1
            records.append(
                {
                    "handle": handle,
                    "url": f"https://shop.kind.co.jp/products/{handle}",
                    "title": product.get("title"),
                    "vendor": product.get("vendor"),
                    "product_type": product.get("product_type"),
                    "source_images": srcs,
                    "local_images": local_names,
                    "is_target": handle == TARGET_HANDLE,
                }
            )

    # Embed every cached photo.
    vectors: dict[str, list[float]] = {}
    for record in records:
        for name in record["local_images"]:
            data = (images_dir / name).read_bytes()
            vec = embed_png(data, backend)
            if vec is None:
                print(f"embed failed for {name}", file=sys.stderr)
                return 1
            vectors[name] = vec

    positives: list[float] = []
    negatives: list[float] = []
    for record in records:
        names = [n for n in record["local_images"] if n in vectors]
        for i, j in _pairs(len(names)):
            positives.append(cosine_similarity(vectors[names[i]], vectors[names[j]]))
    for i, left in enumerate(records):
        for right in records[i + 1 :]:
            ln = [n for n in left["local_images"] if n in vectors]
            rn = [n for n in right["local_images"] if n in vectors]
            if not ln or not rn:
                continue
            # Two pairings per listing pair when possible.
            negatives.append(cosine_similarity(vectors[ln[0]], vectors[rn[0]]))
            if len(ln) > 1 and len(rn) > 1:
                negatives.append(cosine_similarity(vectors[ln[1]], vectors[rn[1]]))
    negatives = negatives[: max(60, len(negatives))]
    positives = positives[: max(30, len(positives))]

    if len(positives) < 30 or len(negatives) < 60:
        print(
            f"not enough pairs: pos={len(positives)} neg={len(negatives)}",
            file=sys.stderr,
        )
        return 1

    candidates = [round(x, 3) for x in [0.70, 0.74, 0.76, 0.78, 0.80, 0.82, 0.84, 0.86, 0.88, 0.90]]
    rows = []
    chosen_t = OPERATING_THRESHOLD
    for thresh in candidates:
        tp = sum(1 for s in positives if s >= thresh)
        fp = sum(1 for s in negatives if s >= thresh)
        tpr = tp / len(positives)
        fpr = fp / len(negatives)
        rows.append({"threshold": thresh, "tpr": round(tpr, 4), "fpr": round(fpr, 4)})
    eligible = [row for row in rows if row["fpr"] <= TARGET_FPR]
    if eligible:
        chosen_t = max(eligible, key=lambda row: (row["tpr"], -row["threshold"]))["threshold"]
    else:
        chosen_t = min(rows, key=lambda row: (row["fpr"], -row["tpr"]))["threshold"]

    tpr = sum(1 for s in positives if s >= chosen_t) / len(positives)
    fpr = sum(1 for s in negatives if s >= chosen_t) / len(negatives)

    receipt = {
        "backbone": BACKBONE_IDENTITY,
        "weights_identity": backend.identity,
        "threshold": chosen_t,
        "target_fpr": TARGET_FPR,
        "tpr": round(tpr, 4),
        "fpr": round(fpr, 4),
        "n_positive_pairs": len(positives),
        "n_negative_pairs": len(negatives),
        "n_listings": len(records),
        "n_images": sum(len(r["local_images"]) for r in records),
        "device": os.environ.get("SEARCHER_EMBEDDING_DEVICE", device),
        "positive_min": round(min(positives), 4),
        "positive_median": round(sorted(positives)[len(positives) // 2], 4),
        "positive_max": round(max(positives), 4),
        "negative_min": round(min(negatives), 4),
        "negative_median": round(sorted(negatives)[len(negatives) // 2], 4),
        "negative_max": round(max(negatives), 4),
        "sweep": rows,
        "fetch_date": FETCH_DATE,
        "source": VENDOR_JSON,
        "target_listing": TARGET_URL,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    target_rec = next(r for r in records if r["is_target"])
    negative_rec = next(r for r in records if not r["is_target"])
    pack = {
        "fetch_date": FETCH_DATE,
        "target_url": TARGET_URL,
        "vendor_json": VENDOR_JSON,
        "listings": records,
        "intent": {
            "text": "Willy Chavarria black long sleeve",
            "tags": ["Willy Chavarria", "shirt"],
            "source_listing": TARGET_URL,
        },
        "reference_images": target_rec["local_images"][:3],
        "true_listing_images": target_rec["local_images"][:3],
        "negative_listing": {
            "url": negative_rec["url"],
            "title": negative_rec["title"],
            "images": negative_rec["local_images"][:3],
        },
    }
    (args.fixtures / "pack.json").write_text(
        json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (args.fixtures / "intent.json").write_text(
        json.dumps(
            {
                "created_at": f"{FETCH_DATE}T00:00:00+00:00",
                "text": pack["intent"]["text"],
                "tags": pack["intent"]["tags"],
                "images": [
                    {"reference_image_id": name, "bytes": name, "width": 512, "height": 512}
                    for name in pack["reference_images"]
                ],
                "budget": {
                    "wall_seconds": 60,
                    "source_limit": 1,
                    "page_limit": 4,
                    "browser_page_limit": 0,
                    "image_limit": 8,
                    "model_call_limit": 0,
                    "byte_limit": 4_000_000,
                },
                "constraints": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (args.fixtures / "listings.json").write_text(
        json.dumps(
            {
                "listings": [
                    {
                        "url": TARGET_URL,
                        "listing_id": TARGET_HANDLE,
                        "title": target_rec["title"],
                        "description": "WILLY CHAVARRIA 無地 ロングスリーブカットソー",
                        "brand": "WILLY CHAVARRIA",
                        "model": TARGET_HANDLE,
                        "price": "8360",
                        "currency": "JPY",
                        "availability": "live",
                        "images": [
                            {"bytes": name, "family_id": name, "role": "unknown"}
                            for name in target_rec["local_images"]
                        ],
                    },
                    {
                        "url": negative_rec["url"],
                        "listing_id": negative_rec["handle"],
                        "title": negative_rec["title"],
                        "description": negative_rec.get("product_type") or "",
                        "brand": negative_rec.get("vendor"),
                        "model": negative_rec["handle"],
                        "price": "10000",
                        "currency": "JPY",
                        "availability": "live",
                        "images": [
                            {"bytes": name, "family_id": name, "role": "unknown"}
                            for name in negative_rec["local_images"]
                        ],
                    },
                ]
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(f"fixtures: {args.fixtures} images={receipt['n_images']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
