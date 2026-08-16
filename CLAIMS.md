# Claim ceiling

The only sentences Searcher is currently entitled to say. Check this
file before any public post. Allowed claims name the evidence that
backs them. If the evidence is a test, that test must still pass.

The Bible's §2.1 list is what Searcher **may** claim after the
corresponding gates pass. Most of those gates have not passed. This
file is the subset that is true of the code today.

The negative list is [LIMITATIONS.md](LIMITATIONS.md).

## Entitled

1. **Searcher accepts images, text, and tags together as a search
   intent, and treats user text as a hypothesis rather than
   authority.**
   Evidence: `src/searcher/api/searches.py`,
   `tests/integration/test_api.py::test_create_returns_immediately`,
   `tests/unit/test_beliefs_aliases_codes.py`.

2. **Uploads are validated by magic bytes. Declared filenames never
   become filesystem paths. EXIF is quarantined after orientation is
   applied.**
   Evidence: `tests/unit/test_upload_validation.py`,
   `src/searcher/reference/imaging.py`.

3. **Searcher compiles alternate product names and multilingual query
   families from the hypothesis portfolio, bounded by the admitted
   source-language table.**
   Evidence: `tests/unit/test_query_compiler.py`,
   `src/searcher/queries/`.

4. **Campaign state persists in SQLite WAL and can be reconstructed
   after interruption.**
   Evidence: `tests/real_runtime/test_crash_resume.py`,
   `tests/real_runtime/test_frontier_sigkill.py`,
   `tests/unit/test_state_transitions.py`,
   `tests/property/test_p06_state_version.py`.

5. **`ITEM_MATCH`, `AUTHENTICITY_CONFIDENCE`, and `LISTING_UTILITY`
   are separately typed. One cannot be substituted for another.
   Public gates read lower bounds.**
   Evidence: `tests/unit/test_judgments.py`,
   `tests/property/test_p12_price_authenticity.py`.

6. **Matching uses classical descriptors, and a learned DINOv2 ViT-S/14
   backbone when a local weights probe succeeds.** VisionMCP at SHA
   `18ee3c06d27f04937d1681dea5fa2650131e4b2a` has no learned feature
   backbone. Searcher uses Pillow descriptors and OpenCV ORB when
   present, plus a structured extractor. The optional backbone is
   DINOv2 ViT-S/14, loaded from a traced TorchScript file at
   `$SEARCHER_DATA_ROOT/models/embedding.pt`, prepared once by
   `scripts/prepare_embedding_weights.py`. A search never downloads
   weights. Availability is the result of a real probe call, not file
   existence. Absent or unreadable weights report unavailable.
   Evidence: `src/searcher/core/embedding_gateway.py`,
   `src/searcher/retrieval/embeddings.py`,
   `docs/architecture/EMBEDDINGS.md`,
   `tests/unit/test_capability_honesty.py`,
   `src/searcher/matching/features.py`,
   `tests/integration/test_matching_pipeline.py`.

7. **Users see two tabs, Real and Possibly Real. Hard vetoes bar
   both. There is no public Fake tab.**
   Evidence: `SEARCHER_BUCKET_POLICY.md`,
   `tests/property/test_p16_hard_veto_bars_both_tabs.py`.

8. **Uncalibrated authenticity intervals are labelled incomplete
   evidence and cannot pass the Real gate under policy `matching-1`.
   Uncalibrated numbers are not shown as percentages.**
   Evidence: `SEARCHER_AUTHENTICITY_POLICY.md`,
   `src/searcher/authenticity/calibration.py`,
   `fixtures/calibration/footwear_v1.json` (`not_field_calibrated: true`).

9. **Outbound fetches allow only `http` and `https`. Localhost,
   private, link-local, and metadata destinations are refused.
   Redirects are re-validated.**
   Evidence: `tests/security/test_ssrf_matrix.py`.

10. **Listing text and pixels that look like instructions are treated
    as data. They do not change tools, policy, or goals.**
    Evidence: `tests/adversarial/test_prompt_injection_listing.py`,
    `tests/adversarial/test_prompt_injection_image.py`,
    `PROMPT_INJECTION_CONTRACT` in `src/searcher/matching/adjudicator.py`.

11. **One campaign cannot read another campaign's private artifacts.**
    Evidence: `tests/property/test_p07_campaign_isolation.py`.

12. **Deletion removes campaign-private objects, events, candidates,
    results, and user text. Receipts and shared content-addressed
    objects remain. Subsequent reads are 404.**
    Evidence: `tests/integration/test_api.py::test_refresh_feedback_delete`,
    [PRIVACY.md](PRIVACY.md).

13. **Registered adapters expose a §14.2 manifest. Adapters marked
    `review_required` ship disabled.**
    Evidence: `tests/unit/test_adapter_manifests.py`,
    [SOURCE_POLICY.md](SOURCE_POLICY.md).

14. **Receipts are hash-chained and verify by recomputation.**
    Evidence: `tests/unit/test_receipts.py`.

15. **The served API does not invent a successful empty search.** A
    campaign that planned no source work, compiled no usable query, or
    fetched nothing stops `BLOCKED` and names what was missing.
    `COMPLETE` means planned coverage was searched and exhausted. An
    empty public result list after real coverage is still an allowed
    honest outcome (`PARTIAL` / `COMPLETE` / `BLOCKED` with coverage),
    not a finding that the item does not exist.
    Evidence: `src/searcher/campaigns/orchestrator.py`,
    `src/searcher/workers/api_campaign.py`,
    `tests/integration/test_terminal_requires_work.py`,
    `tests/integration/test_api.py::test_campaign_runs_to_honest_blocked`.

16. **The Job Scraper §6.10 evasion surface is not present in
    Searcher.**
    Evidence: `tests/unit/test_donor_rejection.py`,
    `src/searcher/integrations/job_scraper/provenance.py`.

17. **There is no hosted Searcher API. The GitHub Pages UI reaches a
    process the operator runs, documented in the README and
    [docs/OPERATING.md](docs/OPERATING.md).**
    Evidence: [README.md](README.md), `web/config.js` (`API_BASE = ""`),
    `scripts/run_api.sh`, `scripts/serve_shared.sh`.

18. **A declared public benchmark exists.** `uv run python -m benchmark
    --all` writes `artifacts/searcher-public-benchmark.receipt.json`.
    The current receipt records recall@1 0.771, recall@5 1.0, MRR 0.867
    over 35 queries, and false Real 0. That is a measured
    retrieval/routing result on the stated splits, not an
    authenticity-accuracy claim.
    Evidence: `artifacts/searcher-public-benchmark.receipt.json`,
    `docs/SEARCHER_BENCHMARK_METHOD.md`.

## Not entitled

Everything in Bible §2.2, restated in [LIMITATIONS.md](LIMITATIONS.md),
plus:

- that a finished live search will produce a Real or Possibly Real result;
- any precision, recall, leakage, cost, or latency number beyond the
  figures recorded in `artifacts/searcher-public-benchmark.receipt.json`;
- that the learned backbone is available when the weights file is
  absent or the probe call fails;
- that the footwear calibration table is a field reliability curve;
- that a blocked source contained no result;
- that a marketplace authentication badge makes a listing authentic;
- that Searcher is a professional authenticator;
- that Searcher covers every brand, category, era, or marketplace;
- that Searcher is better than conventional image search;
- that international adapters are approved for use (they ship disabled);
- that there is a hosted API, telemetry pipeline, or training corpus.

§2.1 items the served API **does** run when live discovery is on
(`scripts/run_api.sh` default): retrieve across the admitted source
classes that accepted the query, compare surviving candidates, explain
the published bucket, and show the last live-check time. A live
campaign commonly finishes `PARTIAL` with real source coverage.
`COMPLETE` is only used after planned coverage was searched.

Still not entitled as a product-wide claim:

- export a replayable search receipt *for every completed live discovery*;
- that every admitted adapter produced coverage (several remain
  `review_required` / disabled).
