#!/usr/bin/env python3
"""Cache KIND listing photos for the known-item fixture pack. No torch."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TARGET_HANDLE = "8001001141404"
TARGET_URL = f"https://shop.kind.co.jp/products/{TARGET_HANDLE}"
VENDOR_JSON = "https://shop.kind.co.jp/collections/willy-chavarria/products.json?limit=250"
UA = (
    "Searcher/0.1.0 (+https://github.com/searcher-project/searcher; "
    "research-discovery; contact=operators@searcher.invalid)"
)
MAX_BYTES = 200_000
MAX_IMAGES = 40


def _get(client: httpx.Client, url: str) -> bytes:
    response = client.get(url, headers={"User-Agent": UA}, timeout=30.0)
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
    return out.getvalue()


def main() -> int:
    dest = ROOT / "fixtures" / "known_item_kind"
    images_dir = dest / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    fetch_date = datetime.now(UTC).date().isoformat()
    with httpx.Client(follow_redirects=True) as client:
        catalog = json.loads(_get(client, VENDOR_JSON))
        products = [p for p in catalog.get("products") or [] if isinstance(p, dict)]
        target = next((p for p in products if p.get("handle") == TARGET_HANDLE), None)
        if target is None:
            print("target listing missing from vendor catalog", file=sys.stderr)
            return 1
        same_type = [
            p
            for p in products
            if str(p.get("product_type") or "") == str(target.get("product_type") or "")
            and p.get("handle") != TARGET_HANDLE
        ]
        chosen = [target] + same_type[:9]
        extras = [p for p in products if p.get("handle") != TARGET_HANDLE and p not in chosen]
        chosen.extend(extras[: 10 - len(chosen)])
        records = []
        saved = 0
        for product in chosen:
            handle = str(product.get("handle"))
            srcs = [str(img["src"]) for img in (product.get("images") or []) if img.get("src")][:3]
            local = []
            for index, src in enumerate(srcs, start=1):
                if saved >= MAX_IMAGES:
                    break
                blob = _shrink(_get(client, src))
                name = f"{handle}_{index}.jpg"
                (images_dir / name).write_bytes(blob)
                local.append(name)
                saved += 1
            records.append(
                {
                    "handle": handle,
                    "url": f"https://shop.kind.co.jp/products/{handle}",
                    "title": product.get("title"),
                    "vendor": product.get("vendor"),
                    "product_type": product.get("product_type"),
                    "source_images": srcs,
                    "local_images": local,
                    "is_target": handle == TARGET_HANDLE,
                }
            )
    target_rec = next(r for r in records if r["is_target"])
    negative_rec = next(r for r in records if not r["is_target"])
    pack = {
        "fetch_date": fetch_date,
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
    (dest / "pack.json").write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {dest} listings={len(records)} images={saved} date={fetch_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
