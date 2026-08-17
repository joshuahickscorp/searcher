# Searcher data model

Bible §39 name. The canonical records are Bible §9. This tree
implements them as Pydantic models in
`src/searcher/contracts/models.py`. Names match the Bible.

## Records present in code

| § | Type | Class |
|---|---|---|
| 9.1 | `SearchIntent` | `SearchIntent` (`SearchConstraints`, `IntentBudget`, `PrivacySettings`) |
| 9.2 | `ReferenceImage` | `ReferenceImage` |
| 9.3 | `ReferenceCrop` | `ReferenceCrop` |
| 9.4 | `ItemHypothesis` | `ItemHypothesis` |
| 9.5 | `VisualSignature` | `VisualSignature` |
| 9.6 | `QueryVariant` | `QueryVariant` |
| 9.7 | `SourcePlan` | `SourcePlan` |
| 9.8 | `FetchAttempt` | `FetchAttempt` |
| 9.9 | `ListingCandidate` | `ListingCandidate` |
| 9.10 | `ListingImage` | `ListingImage` |
| 9.11 | `MatchEvidence` | `MatchEvidence` |
| 9.12 | `AuthenticityEvidence` | `AuthenticityEvidence` |
| 9.13 | `ListingUtility` | `ListingUtility` |
| 9.14 | `BucketDecision` | `BucketDecision` |

Supporting types live in `src/searcher/contracts/primitives.py` and
`src/searcher/contracts/enums.py`: the three judgments, score
intervals, classified facts, public explanation, view hypotheses,
source outcomes, terminal verdicts.

`PrivacySettings.training_opt_in` cannot be constructed as `true`.
Seller-origin text cannot be constructed as `OBSERVED`. OCR /
extractor output cannot be constructed as `OBSERVED`.

## What the API actually exposes

The UI contract is `web/API_EXPECTATIONS.md`. A public result carries
title, source, listing URL, price, size, availability, last checked,
item-match interval, authenticity interval, listing utility, evidence
chips, gaps, and a compare payload. Crops and the hypothesis
portfolio are not represented in the API payload
(`artifacts/searcher-flagship-matched.receipt.json` behaviours 2 and
5: not evaluable).

## Persistence

Campaign rows, events, candidates, and results are SQLite.
User images and derived bytes are content-addressed. Schema is
`migrations/`.

## What is not established

- That every Bible field is populated on every live candidate.
  Several optional fields stay empty when the corresponding lane is
  unavailable (logo detector, learned parts, donor inspect).
- A separate published JSON Schema of the §9 records, outside the
  Pydantic models.
- That the compare ontology on a live garment listing is free of
  leftover footwear part names. Round 2 recorded eyelets / outsole /
  heel on a shirt (`docs/grading/ROUND_2.md`). Later commits
  (`e835379`, `f18dda0`, `3fe276b`) changed profiles and classifiers;
  a fresh live compare dump at this SHA is not in the tree.
