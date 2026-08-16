# Searcher scorecard

Bible §38 dimensions, graded by an independent adversarial pass, with the reopen
history that followed. Nothing here is self-assessed by the code that was graded.

Terminal status under §39: **NOT_READY**.

## Grades

Round 1 was graded on 2026-08-16 at commit `6c4c5e3`, before the fixes it
provoked. Round 2 has not been run: it belongs to a fresh adversarial pass, not
to the author of the fixes.

| Dimension | Round 1 | Why it scored there | Reopened by |
|---|---:|---|---|
| Plan fidelity | 58 | Flagship empty; `COMPLETE` was the empty default; comparison evidence stubbed; ARCHITECTURE said discovery was unwired | `efdd124`, `9f5fa2e` |
| Implementation completeness | 62 | Fetch adapter returned `[]`; completeness measured image count, not view coverage; backbone mis-documented | `efdd124` |
| Real-runtime proof | 45 | 0/21 adversarial recall, all `COMPLETE` in 2s; Dior flagship 0/0; soak and abuse ran with discovery disabled | `9f5fa2e`, `3bb7c61` |
| User-visible proof | 64 | UI, SSE and delete worked; comparison always empty; replica copy false; benchmark copy false | `efdd124`, `4c3be78` |
| Retrieval quality | 38 | FPR 0.59 on the fixtures then in the tree; the shop's own search was never queried | `9f5fa2e`, `5bac368` |
| Authenticity safety | 42 | A replica reached Real through thirteen phrasings — a P0 against §20 | `4c3be78` |
| Security and privacy | 82 | SSRF, upload limits and deletion held; hardening receipts never exercised live discovery; history not yet scrubbed | `cdff1c2` |
| Cost efficiency | 78 | Warm index real on fixtures; the cheap 2s campaign was cheap because it searched nothing | `efdd124`, `9f5fa2e` |
| Test quality | 60 | 316 passing tests that missed findings 1, 5, 6 and 7; the soak asserted `BLOCKED` | `4c3be78`, `efdd124` |
| Documentation | 55 | CLAIMS, LIMITATIONS, ARCHITECTURE, EMBEDDINGS, API, the UI copy and the receipts could not all be true | `efdd124` |

The floor for a critical category is 90. In round 1 nothing reached it.

## What the reopens changed

Each of these is a measured before and after, not a claim of improvement.

| Defect | Before | After |
|---|---|---|
| Replica reaching Real | 13 phrasings published as Real | 0; every phrasing is a regression test |
| Candidate discovery on the live path | 1 imageless collection-feed URL | 18 real product pages, 60 images |
| The flagship scenario | 12 of 24 behaviours met | 21 of 24 |
| Live search results | 0 published | 5 in Possibly Real, true listing ranked first |
| `COMPLETE` with zero fetches | the default terminal | `BLOCKED` with the missing input named |
| `images_compared` on a result | always `[]` | populated, or the reason stated |
| Capability with a dummy weights file | `available: true` | `unavailable`, or `unknown` when unprobed |
| Fast test suite | 228s | 52s |
| Live campaign test | exceeded its 180s timeout | 130s, timeout untouched |

## What is still true and unflattering

- **Nothing reaches Real.** Behaviour 15 of §40 fails. The engine publishes to
  Possibly Real and refuses to promote further, because label views, logo
  resolution and provenance are genuinely missing from these listings. That is
  the gate working, and it is also a product that cannot yet say "this is it".
- **The pair threshold does not separate.** On the splits committed here, 0.86
  admits 70% of different-listing pairs. It is documented as a shortlist cut
  rather than an identity gate. Ranking is what works: recall@1 0.771.
- **Three marketplaces cannot be admitted** without defeating a bot challenge or
  ignoring a robots rule. They stay disabled and say so.
- **The backbone comparison that chose DINOv2 is not reproducible** from this
  repository. The receipt says so in its own body.
- **Round 2 has not been graded.** Until an independent pass regrades, the
  numbers above stand as the current score.

## Regenerating the evidence

```bash
uv run python -m benchmark --all          # retrieval, buckets, calibration, evidence board
uv run python -m benchmark.threshold      # operating point, chosen and held-out
./scripts/flagship_acceptance.py --help   # §40 behaviours against a live campaign
./scripts/test_all.sh                     # both suite invocations
./scripts/scrub_public_tree.sh            # tree and history scrub
```
