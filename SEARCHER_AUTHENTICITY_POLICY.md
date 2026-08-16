# Searcher authenticity policy

The authenticity engine estimates whether available listing evidence is
consistent with an authentic example under a declared category profile. It does
not prove genuineness and it does not accuse a seller.

## Layers

1. Product identity — what the model looks like (item match, separate judgment).
2. Authenticity discriminators — construction, marks, labels, materials.
3. Listing integrity — whether the photographs behave like one coherent listing.

## Output

A calibrated interval, not a point score. Public labels:

- HIGH EVIDENCE
- MODERATE EVIDENCE
- INCOMPLETE EVIDENCE
- CONTRADICTORY EVIDENCE

If calibration data is missing the interval is marked uncalibrated and the
public label is INCOMPLETE EVIDENCE. No uncalibrated percentage is shown.

## What cannot promote authenticity

- price
- source reputation
- a marketplace authentication badge
- seller text, including prompt-injection strings
- duplicate copies of the same photograph

A hard physical contradiction cannot be overridden by any of the above.

## Category profiles

Footwear rules apply only to footwear. Bags, watches, and garments have their
own profiles or a generic empty profile. They do not inherit shoe checks.
