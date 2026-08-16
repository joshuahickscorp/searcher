"""§11.8 visual signature. Cheap descriptors; never a fabricated learned embedding."""

from __future__ import annotations

import json

from searcher.contracts.models import (
    CrossImageLink,
    PartInventoryEntry,
    PartSignature,
    TextObservation,
    VisualSignature,
    VisualSignatureGlobal,
)
from searcher.core.ids import sha256_hex
from searcher.reference.imaging import average_hash, colour_histogram, hamming, silhouette_mask_png


def _descriptor_digest(values: list[float]) -> str:
    payload = json.dumps([round(v, 6) for v in values], separators=(",", ":"))
    return sha256_hex(payload.encode("utf-8"))


def build_signature(
    *,
    image_pngs: dict[str, bytes],
    ocr: list[TextObservation],
    parts: list[PartInventoryEntry],
    dense_features_available: bool,
) -> VisualSignature:
    histograms: dict[str, list[float]] = {}
    hashes: dict[str, str] = {}
    silhouettes: list[str] = []
    for image_id, png in image_pngs.items():
        hist = colour_histogram(png)
        histograms[image_id] = hist
        hashes[image_id] = average_hash(png)
        silhouettes.append(sha256_hex(silhouette_mask_png(png)))
    merged_hist: list[float] = []
    if histograms:
        length = len(next(iter(histograms.values())))
        for i in range(length):
            merged_hist.append(sum(h[i] for h in histograms.values()) / len(histograms))
    links: list[CrossImageLink] = []
    ids = list(image_pngs)
    for i, left in enumerate(ids):
        for right in ids[i + 1 :]:
            dist = hamming(hashes[left], hashes[right])
            similarity = max(0.0, 1.0 - dist / 64.0)
            links.append(
                CrossImageLink(
                    image_a=left,
                    image_b=right,
                    similarity=round(similarity, 4),
                    method="average_hash",
                )
            )
    uncertain = [
        "learned dense embedding unavailable",
        "silhouette is a cheap background-difference, not a product-part mask",
    ]
    if not dense_features_available:
        uncertain.append("DENSE_FEATURES lane blocked; no promotion through this path")
    ocr_terms = [item.text for item in ocr if item.kind != "instruction"]
    logos = [item.text for item in ocr if item.kind == "brand"]
    part_sigs = [
        PartSignature(name=part.part, embedding=None, geometry=None) for part in parts[:12]
    ]
    return VisualSignature(
        global_features=VisualSignatureGlobal(
            silhouette=silhouettes[0] if silhouettes else None,
            embedding=_descriptor_digest(merged_hist) if merged_hist else None,
            colour_distribution=_descriptor_digest(merged_hist) if merged_hist else None,
        ),
        parts=part_sigs,
        distinctive_relations=[],
        uncertain_features=uncertain,
        texture=None,
        ocr_terms=ocr_terms,
        logo_candidates=logos,
        correspondence=links,
        descriptor_kind="cheap_histogram",
        learned_embedding_available=dense_features_available,
    )
