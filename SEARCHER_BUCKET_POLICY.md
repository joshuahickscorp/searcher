# Searcher bucket policy

Users see two tabs: Real and Possibly Real. There is no public Fake tab.

## matching-1 (default for this wave)

Real requires all of:

- item-match lower bound ≥ 0.90
- authenticity lower bound ≥ 0.80
- evidence completeness ≥ 0.65
- authenticity interval is calibrated
- listing is LIVE and the destination was verified
- no hard item contradiction
- no hard authenticity contradiction
- no scam / malicious / replica veto

Possibly Real requires a plausible item match (lower bound ≥ 0.45) and none of
the hard vetoes below.

## Hard vetoes (bar both tabs)

- wrong product
- hard colourway contradiction when exact colour is required
- self-declared replica language
- strong counterfeit evidence (marks/labels vs the authenticity reference)
- image-theft / scam evidence
- malicious URL
- inaccessible destination
- dead listing (`matching-1`)
- duplicate with no independent utility
- insufficient match
- policy refusal

`provisional-1` keeps the Wave 1 gates (dead listings may be Possibly Real;
uncalibrated authenticity may still be routed). Benchmarks swap versions
without a code change.

## Language

“Real” means high confidence under the available images and the current
benchmark. It is not a professional authentication guarantee. Hidden results
are not published as “fake”.
