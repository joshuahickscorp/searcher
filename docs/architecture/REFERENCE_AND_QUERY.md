# Reference analysis and query compilation

Wave 2 and Wave 3 of the Searcher constitution. Later waves consume
`ReferenceAnalysis`, the hypothesis portfolio, and the `QueryVariant` plan.
They do not talk to VisionMCP types.

## VisionMCP

Pinned to `visionmcp-ocular` `0.8.0a2` at SHA
`18ee3c06d27f04937d1681dea5fa2650131e4b2a`.

Primary path: in-process adapter (`searcher.integrations.visionmcp`). The
adapter calls `capabilities_report` / `core_doctor_report` for the light
probe and, when present, `inspect_image` for calibration. It never imports
`visionmcp.receipts.public` (eager compiler/kernels), `ocular`, `torch`,
`cv2`, or Playwright at probe time.

`retrieve_candidates` and `compare_candidate` raise `CapabilityUnavailable`.
They are owned by a later matching wave. Returning placeholder scores is
forbidden.

When the donor is absent or `SEARCHER_VISIONMCP=0`, Searcher still decodes
images with Pillow and still OCRs with host tesseract. Dense features,
product-part segmentation, logo detection, correspondence, and material
analysis stay **blocked**. `promotion_blocked` is set. No result may be
promoted through those lanes.

## Reference analysis

Uploads are hostile. Magic bytes win over declared types. Path names never
enter the object store. EXIF is quarantined. Orientation is applied, then
metadata is stripped. Decompression bombs and oversize dimensions are
typed refusals.

Unification builds a primary cluster and alternate clusters. It does not
block on collage, worn-item, screenshot, or colourway ambiguity.

OCR is `EXTRACTED`. Instruction-like overlay text is recorded as data
(`injection_candidate=True`) and never changes tools, policy, or goals.

The visual signature is a cheap histogram / average-hash / silhouette
descriptor. It is not a learned embedding. The signature says so.

## Hypotheses

User text is a hypothesis (`USER_SUPPLIED`). Visual and OCR evidence can
contradict it. A single low-confidence seller title cannot promote an
alias. Product codes are normalized, distinguished from size codes, and
require region-level OCR or a structured source before promotion.

The active portfolio is bounded (default eight). Weak identities are
archived, not deleted. Contradiction reweights; it does not conclude.

## Queries

Families: exact-name, designer/season, alias, product code, visual,
multilingual, source-specific, negative-research.

Languages: English plus Japanese, Korean, Simplified Chinese, French,
Italian, and Russian, **only** when `docs/sources/SOURCE_RESEARCH_2026-08-16.md`
lists an admitted source that can run that language. Brand names and
product codes stay verbatim when that is what retrieves; algorithmic
transliteration is added as a separate query, never as a rewrite of the
original name.

Negative-research queries gather authentication and adjacent-model
distinctions. They are never used to recommend counterfeit listings.

Generation is bounded. Demoted terms stop producing queries. Later rounds
run only when expected information gain clears the floor.

## CLI

```text
searcher capabilities
searcher reference analyze --image a.png --image b.png --text "…" --tag …
```

The analyze command runs through `PLANNING_QUERIES` and writes
`exports/<search-id>/report.html` plus `report.json`. Source fetching is
not this wave.
