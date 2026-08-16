# Limitations

Searcher is not a professional authenticator. It ranks evidence under a
declared policy version. A result in Real is still an estimate.

This file is the public claim ceiling's negative half. The positive
half is [CLAIMS.md](CLAIMS.md). Product policy lives in
[SEARCHER_AUTHENTICITY_POLICY.md](SEARCHER_AUTHENTICITY_POLICY.md) and
[SEARCHER_BUCKET_POLICY.md](SEARCHER_BUCKET_POLICY.md).

## Prohibited claims (Bible §2.2)

Searcher does **not** claim:

- guaranteed authenticity;
- professional authentication;
- counterfeit detection with universal accuracy;
- exhaustive coverage of the internet;
- access to every marketplace;
- guaranteed purchase availability;
- guaranteed seller trustworthiness;
- guaranteed lowest price;
- universal brand, category, or era coverage;
- superiority over conventional image search without a frozen comparison;
- that a blocked source contained no result;
- that a result is authentic solely because a marketplace says it is authenticated;
- that a result is fake solely because the model is uncertain.

## What Searcher does not do (Bible §2.3)

Searcher does not place orders, enter payment information, negotiate
with sellers, automate bids, bypass age / region / authentication /
access controls, impersonate the user, or publish accusations against
sellers.

## Limitations that are true of this tree today

These are not hypothetical. They are how the code behaves now.

**No learned visual backbone.** VisionMCP at pinned SHA
`18ee3c06d27f04937d1681dea5fa2650131e4b2a` has no learned feature
backbone, no part matcher, and no logo detector. Matching in this
repository is classical (Pillow BRIEF-like descriptors, OpenCV ORB
when present, plus a structured extractor). See
[docs/architecture/MATCHING_AND_AUTHENTICITY.md](docs/architecture/MATCHING_AND_AUTHENTICITY.md).

**No public benchmark has been run.** Real / Possibly Real thresholds
in [SEARCHER_BUCKET_POLICY.md](SEARCHER_BUCKET_POLICY.md) are
provisional. No precision, recall, leakage, or latency figure in this
repository is a measured product result. Do not invent one.

**Uncalibrated intervals degrade.** If the calibration table is
missing, the authenticity interval is labelled `uncalibrated` and the
public label is `INCOMPLETE EVIDENCE`. Uncalibrated numbers are never
shown as percentages. Under policy `matching-1`, uncalibrated
authenticity cannot pass the Real gate. The shipped footwear table
(`fixtures/calibration/footwear_v1.json`) is a synthetic fixture and
records `not_field_calibrated: true`.

**Source coverage is the admitted set only.** See
[SOURCE_POLICY.md](SOURCE_POLICY.md). Grailed, Vestiaire, Depop, and
several others are blocked. A block is recorded as a block, never as
“searched, nothing found.”

**International and review-required adapters ship disabled.** Vinted,
Mercari JP, Yahoo Auctions, Buyee, Bunjang, SSENSE, Farfetch, StockX,
GOAT, Poshmark, and DuckDuckGo HTML are `review_required` and
`enabled=False` until their open questions are closed.

**No hosted API.** The GitHub Pages UI is static files. The engine
runs on the operator's machine and binds `127.0.0.1` by default. See
[README.md](README.md) and [docs/OPERATING.md](docs/OPERATING.md).

**There is no authentication.** Anyone who can reach the process can
create, read, cancel, and delete searches. `--lan` and `--tunnel`
are opt-in and public to whoever has the URL.

**A finished search can honestly return nothing.** Empty Real and
Possibly Real lists are allowed. Hidden candidates are not shown.
That is not a finding that the item does not exist.

**The process is only up while the operator's machine is awake and
the script is running.** Sleep, quit, or a network drop takes it
down. There is no hosted queue.

**CORS is an allowlist.** `SEARCHER_CORS_ORIGINS` must include the
page's origin. A miss looks to the user like “the search service is
unavailable.” The published Pages origin is
`https://joshuahickscorp.github.io` (no `/searcher` path).

**An HTTPS page cannot call an HTTP private origin.** Pointing the
published Pages UI at `http://127.0.0.1` or a LAN `http://` address
is refused by the browser. Local work uses the local copy of the
interface. Sharing over Pages requires an HTTPS API origin (the
tunnel) and the Pages origin on the CORS allowlist.

**Live listing discovery is on in `scripts/run_api.sh`.**
`GET /v1/capabilities` reports `discovery.available` and
`routing.available` from the running process. Some sources still
block (`AUTH_REQUIRED` without operator keys, `SOURCE_UNAVAILABLE`).
Setting `SEARCHER_LIVE_DISCOVERY=0` keeps the honest `BLOCKED` stop
after the reference and query wave. Matching, authenticity, and
ranking packages exist either way.

**No model weights are bundled.** Searcher never downloads them.
The service runs without them and does not promote anything to Real
through a missing-weight fallback. See
[docs/OPERATING.md](docs/OPERATING.md#model-weights).

**The static UI still mentions a “current benchmark.”**
`web/index.html` uses that phrase. No benchmark has been run. The
authoritative statement is this file, not the UI copy. The UI was
not rewritten in this pass.

**Browser sandbox is partial.** Playwright, when installed, launches
headless Chromium with a fresh context, downloads disabled, extensions
disabled, and an honest User-Agent. The code does not set an explicit
deny for clipboard, geolocation, or camera/microphone. There is no
persistent personal profile. See [SECURITY.md](SECURITY.md).

**Calibration and matching are footwear-first.** Other categories do
not inherit shoe checks. They use their own profile or a generic
empty profile.

**eBay and Etsy require operator keys.** Without `EBAY_API_KEY` /
`ETSY_API_KEY` those adapters report `AUTH_REQUIRED`. They do not
scrape the public HTML search pages.

**No purchase, no seller reputation guarantee, no lowest-price
guarantee.** Price may only pull authenticity down. It never proves
genuineness.
