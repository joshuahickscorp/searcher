# Matching and authenticity

Searcher owns the matching stack. VisionMCP at the audited SHA has no learned
feature backbone, no part matcher, and no logo detector. Those lanes stay
blocked. This package implements Stages A–G, the authenticity engine, two-bucket
routing, and ranking.

## Cost hierarchy

Work is recorded on a `CostLedger`. Heavyweight stages (part extraction,
correspondence, browser, deliberative review, remote model, deep authenticity)
raise if they run before deduplication. That is a property test, not a comment.

Order: cache → hashes/metadata → text/OCR → optional global embeddings →
dedupe → local parts → correspondence → (optional) deliberative.

Learned embeddings activate only when weights already exist locally. Nothing
is downloaded. A fresh clone has no weight files. There is no published
Searcher weight file to fetch. Optional paths, if you already have a file:

- `SEARCHER_EMBEDDING_WEIGHTS`
- `$SEARCHER_DATA_ROOT/models/embedding.pt`
- `$SEARCHER_DATA_ROOT/models/clip.pt`

This version loads a traced DINOv2 ViT-S/14 TorchScript module from that
path when a real probe call succeeds. A missing, dummy, or unreadable
file leaves `DENSE_FEATURES` unavailable and `embed_png` returns `None`.
The service runs without weights and answers with classical descriptors.
Nothing is promoted to Real through a missing-weight fallback. Operator
summary: [docs/OPERATING.md](../OPERATING.md#model-weights).

## Three judgments

`ITEM_MATCH`, `AUTHENTICITY_CONFIDENCE`, and `LISTING_UTILITY` stay separately
typed. No path substitutes one for another. Public gates read lower bounds.

## Matching

Classical descriptors (Pillow BRIEF-like, OpenCV ORB when present) plus a
structured extractor: eyelet count, panel count, outsole ratio, heel geometry,
logo placement, label-card hash, colour of the subject.

The part ontology is category data. Footwear is first. A garment profile is
registered so clothing can be added without rewriting the matcher. Unknown
categories do not inherit footwear rules.

The deliberative adjudicator is local and deterministic by default. Its output
is advisory. Listing text is data; the §29.3 contract is attached verbatim.

## Authenticity

Independent of item match. Category profiles are data. Completeness is computed
from expected views. Intervals are calibrated from a fixture table with
recorded provenance. If that table is absent the interval is labelled
`uncalibrated` and the public label is `INCOMPLETE EVIDENCE`. Uncalibrated
numbers are never shown as percentages. Uncalibrated authenticity cannot pass
the Real gate under `matching-1`.

Price may only pull authenticity down.

## Buckets

Policy is versioned (`matching-1`, `provisional-1`). Hard vetoes bar both
public tabs. There is no public Fake tab and no accusatory copy.

## Ranking

Real and Possibly Real have separate orderings. Diversity never changes a
bucket. §21.4 monotonic constraints are functions used by tests and the engine.
