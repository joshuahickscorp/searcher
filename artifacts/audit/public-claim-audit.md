# Public claim audit

Audit of every user-visible string on the Searcher product surface
(`web/` plus every string the served API emits into that surface) for
claims the evidence cannot support.

**Rule under test.** Searcher must never state or imply that it
authenticates. Real is an evidence classification, not a guarantee.
Wording equivalent to authentic, genuine, verified, definitely real,
100%, guaranteed, counterfeit, or fake is an overclaim when it is an
assertion about an item rather than about evidence.

**Opposite failure.** A disclaimer so heavy that the result stops
telling the user anything useful is also a finding.

**This file is a report only.** `web/` and `src/` were not edited.

---

## Method

Surfaces read in full, not sampled:

| Surface | How it reaches a user | How it was read |
| --- | --- | --- |
| `web/index.html` | GitHub Pages and the API-served copy | on disk |
| `web/404.html`, `web/limitations/index.html`, `web/privacy/index.html` | fallback / hash redirects | on disk |
| `web/app.js`, `web/js/*.js` | all dynamic chrome, empty states, banners, Why/Compare copy | on disk |
| `src/searcher/api/views.py` and related API routers | labels, Why text, terminal reasons, hidden notes, errors | `git show HEAD:…` (sparse checkout; `src/` is not on disk) |
| `src/searcher/workers/api_campaign.py`, `src/searcher/campaigns/orchestrator.py` | terminal reasons and SSE warnings the UI prints | `git show HEAD:…` |
| `web/dev/fixtures/**` | same UI, when the development stub is used | on disk |

Claim ceiling used as the entitled vocabulary:

- `CLAIMS.md` (what the tree may say)
- `LIMITATIONS.md` / `SEARCHER_AUTHENTICITY_POLICY.md` / `SEARCHER_BUCKET_POLICY.md`
- Engine public labels in `src/searcher/authenticity/contracts.py`
  (`HIGH EVIDENCE`, `MODERATE EVIDENCE`, `INCOMPLETE EVIDENCE`,
  `CONTRADICTORY EVIDENCE`)

Classification:

| Tag | Meaning |
| --- | --- |
| **OVERCLAIM** | Asserts or implies authenticity, genuineness, verification of the item, certainty, a guarantee, or that an item is counterfeit/fake. |
| **USELESS** | So hedged, generic, or contradictory that the reader cannot act. |
| **WATCH** | Entitled in context, easy to misread if the framing is stripped. |
| **HONEST** | Evidence-framed, operational, or a prohibition. |
| **NEUTRAL** | Chrome with no claim about an item. |

Operator docs (`README.md`, `CLAIMS.md`, `LIMITATIONS.md`) and
developer contracts (`web/README.md`, `web/API_EXPECTATIONS.md`) are
not product UI. They were used only as the ceiling.

---

## Verdict

The live results drawer does **not** say “authentic”, “genuine”,
“verified item”, “definitely real”, “100%”, “guaranteed authentic”,
or “fake” about a listing. There is no public Fake tab. The standing
disclaimer — “Real is an evidence ranking, not a professional
authentication guarantee.” — is one sentence and still leaves the
ranking usable.

The product does overclaim in four places that matter:

1. The Limitations page says replica sources **are** searched, then
   explains they are **not**.
2. The public authenticity label is the bare word **High**, not the
   entitled phrase **HIGH EVIDENCE**.
3. Limitations defines Real using retrieval-benchmark figures,
   including **false Real 0**, which `CLAIMS.md` forbids treating as
   an authenticity-accuracy claim.
4. The home lead promises to “find the exact item”.

The opposite failure is real but narrower: one leftover “some
candidates did not meet policy” sentence, reason-code jargon glued
onto otherwise honest Why text, and a Limitations paragraph that is
too dense to use.

---

## Overclaim findings

### O1. Limitations says replica sources are searched

| | |
| --- | --- |
| File:line | `web/index.html:124` |
| Current | `Replica sources are searched to find replicas. A replica listing can never be ranked Real.` |
| Why it overclaims | The first sentence is false on this tree. The same page, 20 lines later (`web/index.html:143–162`), is titled “Why replica sources are not searched” and says Searcher “does not, however, search replica marketplaces” and that “the result is no replica coverage at all”. The replica tab is withdrawn from the header (`web/index.html:22–24`). A reader who stops at line 124 is told Searcher hunts replicas. |
| Suggested | `Searcher does not search replica marketplaces. If a listing from an admitted source describes itself as a replica, it can be listed under Replica and can never be ranked Real.` |

The second clause (“can never be ranked Real”) is a ranking rule the
engine enforces (`src/searcher/campaigns/publication.py`). Keep it.
It is not an assertion that the item is fake.

### O2. Public authenticity value is “High”, not “HIGH EVIDENCE”

| | |
| --- | --- |
| File:line | `src/searcher/api/views.py:285–296` (emitted); `web/js/results.js:154` (rendered as `Authenticity evidence: High`) |
| Current | `_judgment_label` returns `High` / `Moderate` / `Incomplete evidence` / `Contradictory`. The same helper labels both item-match and authenticity. |
| Why it overclaims | `SEARCHER_AUTHENTICITY_POLICY.md` and `src/searcher/authenticity/contracts.py:11–14` entitle only `HIGH EVIDENCE`, `MODERATE EVIDENCE`, `INCOMPLETE EVIDENCE`, `CONTRADICTORY EVIDENCE`. The UI prefix “Authenticity evidence” helps, but the value the eye lands on is the single word **High**. That reads as “highly authentic”, not “high evidence”. Uncalibrated intervals are supposed to stay `INCOMPLETE EVIDENCE`; the remapping also drops the word “evidence” from the high/moderate rungs. |
| Suggested | Emit the engine labels unchanged: `HIGH EVIDENCE`, `MODERATE EVIDENCE`, `INCOMPLETE EVIDENCE`, `CONTRADICTORY EVIDENCE`. Keep a separate item-match vocabulary (`Strong match` / `Plausible match` / `Incomplete match`) so the two judgments cannot collapse into one adjective. |

Same wording is baked into the development stub, which the Pages UI
can be pointed at:

- `web/dev/fixtures/results/res-real-1.json:35–36` — `"authenticity": { "label": "High" }`
- `web/dev/fixtures/results/res-real-2.json:35` — same
- `web/dev/fixtures/results/res-possible-2.json` — authenticity `"Moderate"`
- `web/API_EXPECTATIONS.md:192–195` documents `High` as the contract

### O3. Limitations defines Real with retrieval numbers, including “false Real 0”

| | |
| --- | --- |
| File:line | `web/index.html:123` |
| Current | `Real means high confidence this is the same item under the available evidence and the published benchmark in artifacts/searcher-public-benchmark.receipt.json (recall@1 0.771, recall@5 1.0, MRR 0.867 over 35 queries, false Real 0) — not a professional authentication guarantee.` |
| Why it overclaims | `CLAIMS.md` §18: those figures are “a measured retrieval/routing result on the stated splits, **not an authenticity-accuracy claim**.” Putting `false Real 0` inside the definition of the Real tab tells a reader Searcher never wrongly calls a listing real. The receipt does not support that as an authenticity claim. The same sentence is also **USELESS** (U1): path, four metrics, and a disclaimer bury the meaning. |
| Suggested | `Real means the listing cleared the published evidence gate under the current policy. It is not a professional authentication. The retrieval benchmark that policy cites is in artifacts/searcher-public-benchmark.receipt.json; those numbers are retrieval/routing, not authenticity accuracy.` |

### O4. Home lead claims the exact item

| | |
| --- | --- |
| File:line | `web/index.html:11` (meta description); `web/index.html:31` (on-page lead) |
| Current | `Find the exact item, not merely something similar.` |
| Why it overclaims | “Exact” is a certainty the entitled retrieval numbers do not support (recall@1 0.771 on 35 queries). It is identity language, not the word “authentic”, but a visitor reads it as a guarantee of the same physical item. |
| Suggested | `Search admitted sources for the same item, from photographs.` |

### O5. “Why Real” presents the ranking as a fact to be justified

| | |
| --- | --- |
| File:line | `src/searcher/api/views.py:587` (`Why Real` / `Why Possibly Real`); stub `web/dev/fixtures/results/res-real-1.json:65` (`Why Real`); stub `res-possible-1.json:65` (`Why Possible`) |
| Current | Heading `Why Real` is the first line of the card lead (`web/js/results.js:106`). |
| Why it overclaims | The heading treats “Real” as a property of the listing. The entitled reading is “why this listing is in the Real list”. |
| Suggested | `Why this is in Real` / `Why this is in Possibly Real` / `Why this is in Replica`. |

The live `tab_reason` that follows is honest
(`src/searcher/api/views.py:588`: “This listing met the Real gate
under the available evidence.”). Keep that sentence; change the
heading.

### O6. Raw reason codes, including `STRONG_COUNTERFEIT_EVIDENCE`, are appended to the card lead

| | |
| --- | --- |
| File:line | `src/searcher/api/views.py:594–595`; rendered by `web/js/format.js:170–176` → `web/js/results.js:107` |
| Current | `tab_reason = f"{tab_reason} Reason codes: {', '.join(decision.reason_codes)}."` |
| Why it overclaims | The card lead is the one sentence a user reads without opening Full evidence. Glueing `STRONG_COUNTERFEIT_EVIDENCE` or `SELF_DECLARED_REPLICA` onto it uses “counterfeit” / “replica” as an assertion about the item. Hard-veto codes are meant to hide a result, not to caption a published one; if a code leaks onto Replica or a mis-bucketed card, the user sees an accusation. Even benign codes (`INSUFFICIENT_MATCH`) turn a human sentence into operator jargon (**USELESS**, U3). |
| Suggested | Never append raw codes to `tab_reason`. Map published codes through `_HIDDEN_REASON_WORDS` (already evidence-framed at `src/searcher/api/views.py:109–120`) or omit them from the public lead. |

`_HIDDEN_REASON_WORDS["STRONG_COUNTERFEIT_EVIDENCE"]` is already the
honest form: “marks contradict the reference”
(`src/searcher/api/views.py:114`). That is about evidence. Use it.

### O7. Terminal reason “success saturation”

| | |
| --- | --- |
| File:line | `src/searcher/campaigns/orchestrator.py:1466` (`"success saturation"`); stub `web/dev/fixtures/searches/fixture-normal.json` (`Success saturation: Real results exist and additional work had low expected gain.`) |
| Current | Live: `success saturation`. Stub: `Success saturation: Real results exist…` |
| Why it overclaims | “Success” plus “Real results exist” reads as “we found authentic items.” The engine means the Real-list saturation budget was hit. |
| Suggested | `Stopped because the Real list reached its saturation limit. That is a budget stop, not a certificate.` |

---

## Uselessness findings

### U1. Real’s definition is too dense to use

| | |
| --- | --- |
| File:line | `web/index.html:123` |
| Current | See O3. One sentence contains the definition, a repo path, four benchmark figures, and a disclaimer. |
| Why it is useless | A reader who needs to know what the tab means cannot extract it. The disclaimer at the end is easy to miss after the numbers. |
| Suggested | Same replacement as O3. Put the receipt citation on its own line, labelled as retrieval. |

### U2. Limitations promises the interface will not say why candidates were hidden

| | |
| --- | --- |
| File:line | `web/index.html:164` |
| Current | `A missing candidate is simply absent. If some candidates did not meet policy, that is all the interface will say.` |
| Why it is useless | This is the sentence `tests/unit/test_hidden_reason_note.py` exists to kill. The live API now names the gates
  (`src/searcher/api/views.py:123–147`: “Hidden: 2 because the evidence did not establish the same item; 1 because the listing is no longer offered.”). The page still tells the user they will learn nothing. |
| Suggested | `Hidden listings are not shown. When any were hidden, the results panel names the most common reasons — for example that the evidence did not establish the same item, or that the listing is no longer offered. That is not a finding that the item does not exist.` |

UI fallback still emits the old generic line when the API sends no
note: `web/js/results.js:478–479`
(`"Some candidates did not meet policy."`). Stub searches
`web/dev/fixtures/searches/fixture-normal.json` and
`fixture-empty-real.json` still ship that note.

### U3. Reason codes on the Why lead

Covered with O6. The human sentence is usable until the codes are
appended; then it stops being something a buyer can act on.

### U4. “Not provided by the search service.” when many Why fields are empty

| | |
| --- | --- |
| File:line | `web/js/format.js:104`; used at `web/js/results.js:51–56, 62, 80, 88` and `web/js/compare.js:108, 129` |
| Current | Empty Why/Compare lists render `Not provided by the search service.` |
| Why it is useless | Honest, but if comparison did not run the user sees a stack of the same sentence and no next step. The compare path already has a better empty reason (`comparison stage did not run`, `web/js/results.js:70` / `src/searcher/api/views.py:408`). |
| Suggested | Prefer the specific empty reason already computed (`images_compared_reason`, `compare.reason`). Reserve the generic fallback for a single line, not every heading. |

### U5. Hedging is stacked, but the ranking still survives

The results drawer currently shows, at once:

1. Footer: `Not a professional authenticator.` (`web/index.html:170`)
2. Persistent drawer line: `Real is an evidence ranking, not a professional authentication guarantee.` (`web/index.html:201–203`)
3. Tab subtitle with the same hedge (`web/js/format.js:111–112`)
4. Every card: `Still unverified` / `No physical inspection.` (`src/searcher/api/views.py:608`, `web/js/results.js:56`)

That is four restatements of “we did not authenticate.” It is **not**
useless: the tab still says Real or Possibly Real, the subtitle still
says what the gate means, and the card lead still says whether the
gate was met. Do not add a fifth hedge. If anything is cut, cut the
per-card “Still unverified” boilerplate (it is true of every result)
and keep the one drawer sentence.

---

## Watch (entitled, easy to misread)

These are allowed by the claim ceiling. They become overclaims only
if the framing around them is removed.

| File:line | Wording | Why it is entitled | How it goes wrong |
| --- | --- | --- | --- |
| `web/index.html:207` | Tab label `Real` | `CLAIMS.md` §7 and `SEARCHER_BUCKET_POLICY.md` name the tabs Real and Possibly Real. There is no Fake tab. | The bare word, with the subtitle hidden on a narrow viewport, reads as “this item is real”. The drawer disclaimer (`web/index.html:202`) is what keeps it a classification. |
| `web/js/format.js:111–112` | `High confidence this is the same item under the current evidence — not a professional authentication guarantee.` | Bucket policy: “Real means high confidence under the available images… It is not a professional authentication guarantee.” | “High confidence” + “same item” is identity, not authenticity, but sits under a tab named Real. Keep the em-dash clause. |
| `web/js/format.js:114–115` | `May be the same item; evidence is missing or conflicting.` | Honest Possibly Real. | Fine. |
| `web/js/format.js:117–118` | `From replica sources. A replica listing can never be ranked Real.` | Ranking rule, not an accusation. Matches `SEARCHER_BUCKET_POLICY.md`. | “From replica sources” is false for the default UI (replica sources are not searched). Prefer: `Listed as Replica because of the listing’s own language or source family. It cannot be ranked Real.` |
| `web/index.html:145–146` | `Searcher can rank a listing as Replica` | True of the engine when `?scopes=` includes replica or a listing self-declares. | Default visitors never see the Replica tab (`web/index.html:212` is `hidden`; header control withdrawn). Say “can, when replica scope is on or the listing declares a replica”. |
| `web/js/format.js:10` / `src/searcher/api/views.py:35` | Stage `Checking listing authenticity evidence` | About evidence, not a verdict. | Fine. |
| `web/js/format.js:11` / `src/searcher/api/views.py:36` | Stage `Verifying live links` | “Verifying” here is HTTP reachability (`LIVE_CHECKING`). | Easy to hear as “verifying the item”. Prefer `Checking that listing links still resolve`. |
| `web/js/results.js:56` | Heading `Still unverified` | Points at `why.still_unverified`. | Sounds like an unfinished authentication. Prefer `Not physically inspected`. |
| `web/js/feedback.js:58` / `web/js/format.js:126–134` | `Is this the item?` / `This is the one` / `This is not it` | User identity feedback. API records it and does not re-rank (`web/js/feedback.js:13`, `src/searcher/api/feedback.py` `applied: False`). | Not Searcher speaking. Keep. |
| `web/index.html:122, 126–139, 170` | “not a professional authenticator”, prohibited-claim list | The negative half of the ceiling. “Fake” and “authentic” appear only as things Searcher does **not** claim. | Fine. Do not shorten the list into a slogan that says “we detect fakes”. |
| `src/searcher/api/views.py:113` | Hidden note `the seller describes a replica` | About seller text, not a finding that the item is fake. | Fine. |
| `src/searcher/api/views.py:114` | Hidden note `marks contradict the reference` | Evidence vs reference. Avoids “counterfeit”. | Fine. This is the model for O6. |
| `src/searcher/api/views.py:608` | `No physical inspection.` | Always true, always honest. | Boilerplate (see U5). |

---

## Honest strings that look like the danger words and are not

Checked on purpose because they contain authentic / real / verified /
replica / fake in some form:

| File:line | Wording | Why it is not an overclaim |
| --- | --- | --- |
| `web/index.html:202` | `Real is an evidence ranking, not a professional authentication guarantee.` | The required framing. One sentence. Keep. |
| `web/index.html:122` | `Searcher is not a professional authenticator. … A result in Real is still an estimate.` | Negative claim + “estimate”. |
| `web/index.html:138–139` | does not claim a result is authentic because a marketplace authenticated it, or fake because the model is uncertain | Prohibitions, not assertions. |
| `web/index.html:143–162` | Why replica sources are not searched; Taobao / Weidian / Yupoo + robots; absence is never evidence | Meets `tests/unit/test_interface_explains_replica_absence.py`. This block is the honest replica story. O1 is the sentence that contradicts it. |
| `web/js/format.js:120–124` | `No candidate met the Real threshold yet.` / `Searcher did not find a displayable candidate within this search’s current source and budget coverage.` | Threshold / coverage, not “the item does not exist”. |
| `web/js/results.js:463` | `Search blocked. … This is not the same as finding no matching item.` | Explicitly blocks the dangerous reading. |
| `web/js/results.js:465` | `Search failed from an internal error. It is not a “no results” outcome.` | Same. |
| `src/searcher/workers/api_campaign.py:73–76` | `Live listing discovery is not available in this process. Reference analysis finished. This is not a finding that the item does not exist.` | Honest BLOCKED. |
| `src/searcher/campaigns/orchestrator.py:1552` | `The search failed because of an internal error. This is not a no-results outcome.` | Honest FAILED. |
| `src/searcher/api/views.py:588` | `This listing met the Real gate under the available evidence.` | Gate + evidence. This is the model public sentence. |
| `src/searcher/api/views.py:590` | `The item may match, but important evidence is missing or conflicting.` | Matches the Possibly Real subtitle. |
| `src/searcher/api/views.py:225–231` | Keyhole note: walked catalogues, `absence is not evidence of absence` | Prevents a coverage miss from reading as a finding. |
| `src/searcher/authenticity/contracts.py:11–14` | `HIGH EVIDENCE` … | Entitled labels. Not what the API currently emits (O2). |
| `web/js/results.js:51` | `Why does Searcher think this is the same item?` | Identity question, not authenticity. |
| `web/js/results.js:154` | Score line title `Authenticity evidence` | Correct framing. The **value** is the problem (O2). |

No user-visible string says “genuine”, “definitely real”, “100%”,
“guaranteed authentic”, or uses “fake” / “counterfeit” as a verdict
about a listing. “Fake” appears only in the Limitations prohibition
list (`web/index.html:139`). “Counterfeit” appears only there
(`web/index.html:129`) and as an internal reason-code name that O6
can leak.

---

## Full inventory

Every user-visible string, by surface. Suggested replacements appear
only where the verdict is OVERCLAIM or USELESS.

### A. `web/index.html` — first screen, docs, chrome

| Line | Wording | Verdict |
| --- | --- | --- |
| 10 | `<title>SEARCHER</title>` | NEUTRAL |
| 11 | `Find the exact item, not merely something similar.` | **OVERCLAIM** (O4) |
| 16 | `Skip to search` | NEUTRAL |
| 21 | `SEARCHER` (wordmark) | NEUTRAL |
| 31 | `Find the exact item, not merely something similar.` | **OVERCLAIM** (O4) |
| 33 | `Images` | NEUTRAL |
| 48 | `Drop, click, or paste` | NEUTRAL |
| 50 | `1 to 10 JPEG, PNG, WebP, or GIF photographs. The server is the final validator.` | HONEST |
| 51 | `1 to 10 raster images. The server is the final validator.` (sr-only) | HONEST |
| 54 | `Selected images` | NEUTRAL |
| 58 | `Name` | NEUTRAL |
| 65 | placeholder `If you know` | NEUTRAL |
| 72 | `What you know about it` | NEUTRAL |
| 76 | `Tags` | NEUTRAL |
| 78 | `Current tags` | NEUTRAL |
| 85 | placeholder `Add a tag` | NEUTRAL |
| 89 | `Comma or Enter creates a tag. Backspace removes the last one.` | NEUTRAL |
| 93 | `Search` | NEUTRAL |
| 99 | `Recent searches on this device` | NEUTRAL |
| 105 | `Privacy` | NEUTRAL |
| 106 | `Searcher treats a search as a private request, not as content to publish or train on.` | HONEST |
| 108 | `Uploads are private by default. They are sent only to the configured search service.` | HONEST |
| 109 | `Images, text, and tags are not used for training by default.` | HONEST |
| 110 | `This site has no hidden analytics, no accounts, and no third-party scripts.` | HONEST |
| 111 | `Nothing here is uploaded to a third-party model unless the search service is explicitly configured that way.` | HONEST |
| 112 | `A search can be deleted. Deletion is requested from the results panel when a search is open.` | HONEST |
| 113 | `Retention is a property of the search service, not of this page. This page stores only local drafts, display preferences, and recent search identifiers in this browser.` | HONEST |
| 114 | `Diagnostics should be inspectable before anything is exported. This page never embeds a secret, token, or credential.` | HONEST |
| 116 | `The static files of this interface contain no keys. The API address is deployment configuration, overridable with a ?api= query parameter for local testing.` | HONEST |
| 117 | `Back to search` | NEUTRAL |
| 121 | `Limitations` | NEUTRAL |
| 122 | `Searcher is not a professional authenticator. It ranks evidence under a declared policy and shows calibrated uncertainty. A result in Real is still an estimate.` | HONEST |
| 123 | Real = high confidence + receipt figures including `false Real 0` | **OVERCLAIM** (O3) and **USELESS** (U1) |
| 124 | `Replica sources are searched to find replicas. A replica listing can never be ranked Real.` | **OVERCLAIM** (O1) on the first sentence; second sentence WATCH |
| 126–139 | “Searcher does not claim:” list (guaranteed authenticity, professional authentication, counterfeit detection, coverage, purchase, seller trust, lowest price, brand/era, superiority, blocked source, marketplace-authenticated ⇒ authentic, uncertain ⇒ fake) | HONEST (prohibitions) |
| 141 | No orders, no payment, no seller accusations; listings open in a new tab; checkout is never embedded | HONEST |
| 143 | `Why replica sources are not searched` | HONEST |
| 145–148 | Can rank Replica; does not search replica marketplaces; fetch limit, not a software limit | HONEST / WATCH (see table) |
| 151–158 | Taobao / Weidian / Yupoo robots reasons; no replica coverage at all | HONEST |
| 161–162 | Absence of replica results is never evidence that no replica exists | HONEST |
| 164 | `A missing candidate is simply absent. If some candidates did not meet policy, that is all the interface will say.` | **USELESS** (U2) |
| 165 | `Back to search` | NEUTRAL |
| 170 | `Not a professional authenticator.` · Privacy · Limitations | HONEST |
| 175 | `Results` | NEUTRAL |
| 179 | `Cancel search` | NEUTRAL |
| 180 | `Delete this search` | NEUTRAL |
| 181 | `Close results` | NEUTRAL |
| 192 | `All stages` | NEUTRAL |
| 202 | `Real is an evidence ranking, not a professional authentication guarantee.` | HONEST — keep |
| 205 | `Result lists` | NEUTRAL |
| 207 | `Real` | WATCH |
| 210 | `Possibly Real` | HONEST |
| 213 | `Replica` (hidden unless replica scope on) | WATCH |
| 232 | `Coverage` | NEUTRAL |
| 239 | `Developer numbers` | NEUTRAL |
| 245 | `Compare` | NEUTRAL |
| 246 | `Close` | NEUTRAL |

### B. Redirect pages

| File:line | Wording | Verdict |
| --- | --- | --- |
| `web/404.html:31` | `Taking you to SEARCHER…` / `Continue` | NEUTRAL |
| `web/privacy/index.html:6,10` | `Privacy — SEARCHER` / `Continue to Privacy` | NEUTRAL |
| `web/limitations/index.html:6,10` | `Limitations — SEARCHER` / `Continue to Limitations` | NEUTRAL |

### C. Dynamic chrome — `web/js/format.js`

| Line | Wording | Verdict |
| --- | --- | --- |
| 2 | `Understanding the item` | NEUTRAL |
| 3 | `Reading visible labels` | NEUTRAL |
| 4 | `Building possible identities` | NEUTRAL |
| 5 | `Searching exact names` | NEUTRAL (query type, not a guarantee) |
| 6 | `Searching alternate names` | NEUTRAL |
| 7 | `Searching international sources` | NEUTRAL (coverage can still be empty) |
| 8 | `Comparing candidate images` | NEUTRAL |
| 9 | `Checking detail consistency` | NEUTRAL |
| 10 | `Checking listing authenticity evidence` | HONEST |
| 11 | `Verifying live links` | WATCH |
| 12 | `Ranking results` | NEUTRAL |
| 44 | `check time not provided` / `just now` / relative times | NEUTRAL |
| 67–71 | `Live` / `Sold` / `Reserved` / `Removed` / `Availability unknown` | HONEST (listing state) |
| 74 | `… — never checked` | HONEST |
| 79, 83 | `Price not provided` | HONEST |
| 87, 90 | `Size not provided` / `Size {marked}` | NEUTRAL |
| 104 | `Not provided by the search service.` | **USELESS** when stacked (U4); honest as a single fallback |
| 111–112 | Real subtitle (high confidence + not a professional guarantee) | WATCH |
| 114–115 | Possibly Real subtitle | HONEST |
| 117–118 | Replica subtitle | WATCH |
| 120–121 | `No candidate met the Real threshold yet.` | HONEST |
| 123–124 | `Searcher did not find a displayable candidate within this search’s current source and budget coverage.` | HONEST |
| 126–134 | `This is the one` / `This is not it` | WATCH (user speech) |
| 154 | `Add a photograph of the {view}.` / `Add the missing photograph the search named.` | HONEST |
| 198 | `Stage N of 11` | NEUTRAL |
| 213–217 | `{n} sources searched` / `in progress` / `blocked` / `pages` / `listings seen` | HONEST |
| 233–237 | `Finished` / `Finished with incomplete coverage` / `Blocked` / `Failed` / `Cancelled` | HONEST |

### D. Dynamic chrome — `web/js/results.js`

| Line | Wording | Verdict |
| --- | --- | --- |
| 27 | `Not provided` (score without a label) | HONEST |
| 50 | `Why this result` (fallback heading) | HONEST |
| 51 | `Why does Searcher think this is the same item?` | HONEST |
| 52 | `Why is it in this tab?` | HONEST |
| 53 | `Which evidence supports the decision?` | HONEST |
| 54 | `Which evidence conflicts?` | HONEST |
| 55 | `What evidence is missing?` | HONEST |
| 56 | `Still unverified` | WATCH |
| 56 | empty contradictions → `None stated.` | HONEST |
| 59 | `Is the listing currently live?` | HONEST |
| 60 | `Yes, when last checked.` / `No, or not confirmed.` | HONEST |
| 61 | `When was it checked?` | HONEST |
| 65 | `Which images were compared?` | HONEST |
| 70 | `comparison stage did not run` | HONEST |
| 78 | `Did multiple result pages reuse the same images?` | HONEST |
| 81–82 | `Yes — N shared image families.` / `No shared image families were reported.` | HONEST |
| 86 | `What is reported by the seller rather than independently observed?` | HONEST |
| 96 | `Full evidence` | HONEST |
| 115 | `What to add next` | HONEST |
| 143 | `Untitled listing` | NEUTRAL |
| 144 | `Source: …` / `Source not provided` | HONEST |
| 153 | `Item match` | HONEST |
| 154 | `Authenticity evidence` | HONEST (label); value may OVERCLAIM (O2) |
| 155 | `Listing utility` | HONEST |
| 175 | `Open listing ↗` | NEUTRAL |
| 179 | `No usable listing link was recorded.` | HONEST |
| 184 | `This listing is no longer offered; the link opens the original page.` | HONEST |
| 189 | `Availability could not be confirmed, so the link may be stale.` | HONEST |
| 192 | `Compare` | NEUTRAL |
| 210–211 | Coverage `Completed` / `Blocked` | NEUTRAL |
| 217, 228 | `None.` | NEUTRAL |
| 226 | `Missing views` | HONEST |
| 234 | `Deeper refresh` | NEUTRAL |
| 236–238 | `Deeper refresh is available.` / `… is not available.` | HONEST |
| 241 | `Pages fetched: … Candidates normalized: …` | HONEST |
| 344 | `Search finished` / `Starting` | NEUTRAL |
| 406 | `Close results, add another photograph or a more specific name, and search again.` | HONEST |
| 441 | `See Possibly Real.` | HONEST |
| 448 | `No Possibly Real candidates yet.` | HONEST |
| 461 | `Search cancelled. Evidence gathered before cancellation is kept.` | HONEST |
| 463 | `Search blocked. … This is not the same as finding no matching item.` | HONEST |
| 465 | `Search failed from an internal error. It is not a “no results” outcome.` | HONEST |
| 467 | `Search finished with incomplete coverage. Some sources were blocked or the budget ended first.` | HONEST |
| 478–479 | `Some candidates did not meet policy.` | **USELESS** (U2 fallback) |
| 586–588 | announced `Real tab` / `Possibly Real tab` / `Replica tab` | WATCH / HONEST |

### E. Dynamic chrome — other `web/` scripts

| File:line | Wording | Verdict |
| --- | --- | --- |
| `web/js/form.js:62` | `Remove` | NEUTRAL |
| `web/js/form.js:76` | `{n} of 10 photographs` | NEUTRAL |
| `web/js/form.js:93` | `{file} is not a supported raster image. Use JPEG, PNG, WebP, or GIF. The server is the final validator.` | HONEST |
| `web/js/form.js:97` | `{file} is larger than 20 MB. The server is the final validator.` | HONEST |
| `web/js/form.js:101` | `A search can include at most 10 images. The server is the final validator.` | HONEST |
| `web/js/form.js:106` | `{file} is already attached.` | NEUTRAL |
| `web/js/form.js:147` | `None yet on this device.` | NEUTRAL |
| `web/js/form.js:200` | `Add at least one image to search. The server is the final validator.` | HONEST |
| `web/js/form.js:225` | `Searching` / `Search` | NEUTRAL |
| `web/js/feedback.js:6` | `Recording…` | NEUTRAL |
| `web/js/feedback.js:13` | `{This is the one\|This is not it} recorded. Rankings are unchanged.` | HONEST |
| `web/js/feedback.js:15` | `Feedback could not be recorded.` | HONEST |
| `web/js/feedback.js:58` | `Is this the item?` | WATCH |
| `web/js/compare.js:18–24` | `Reported by seller` / `Reported by source` / `User supplied` / `Observed` / `Extracted` / `Inferred` / `Unresolved` | HONEST |
| `web/js/compare.js:86` | `Your reference` | NEUTRAL |
| `web/js/compare.js:90` | `Candidate` | NEUTRAL |
| `web/js/compare.js:97–100` | `Part` / `Note` / `Status` / `Origin` | NEUTRAL |
| `web/js/compare.js:123` | `Seller-reported fields` | HONEST |
| `web/js/compare.js:145–147` | `Supporting details` / `Contradictions` / `Missing views` | HONEST |
| `web/js/dom.js:91, 98` | `Image unavailable` | NEUTRAL |
| `web/js/api.js:31` | `The search service is unavailable.` | HONEST |
| `web/js/api.js:48` | `Request failed ({status})` | HONEST |
| `web/app.js:89–91` | `The search service is unavailable. Searcher cannot start or update a search until the service responds.` | HONEST |
| `web/app.js:129` | `The live update connection dropped. Reconnecting…` | HONEST |
| `web/app.js:176` | fallback hidden note `Some candidates did not meet policy.` | **USELESS** (U2) |
| `web/app.js:181` | `The search reported a warning.` | HONEST |
| `web/app.js:188` | `Search finished.` | NEUTRAL |
| `web/app.js:203` | `Feedback recorded. Rankings are unchanged.` | HONEST |
| `web/app.js:259` | `Search cancelled.` | NEUTRAL |
| `web/app.js:276` | `Search deleted.` | NEUTRAL |
| `web/app.js:354, 357` | `Search could not be started.` | HONEST |
| `web/app.js:396–397` | `This search is no longer available. It may have been deleted.` | HONEST (does not say “no results”) |
| `web/app.js:409` | `Privacy — SEARCHER` / `Limitations — SEARCHER` | NEUTRAL |
| `web/app.js:439` | unavailable banner + `Set a working ?api= address if this page is not served by the search service.` | HONEST |

`web/js/router.js`, `web/js/storage.js`, `web/js/scopes.js`,
`web/config.js` emit no user-facing claim copy. Scope checkboxes are
absent from the DOM.

### F. Live API strings the UI prints

Emitted by the served process. `src/` was read via `git show HEAD:…`.

#### Result projection — `src/searcher/api/views.py`

| Line | Wording | Verdict |
| --- | --- | --- |
| 21–42 | Stage map (same eleven phrases as `format.js`) | same as C |
| 110 | `the evidence did not establish the same item` | HONEST |
| 111 | `the listing could not be reached` | HONEST |
| 112 | `the listing is no longer offered` | HONEST |
| 113 | `the seller describes a replica` | HONEST |
| 114 | `marks contradict the reference` | HONEST |
| 115 | `the photographs appear taken from elsewhere` | HONEST |
| 116 | `the destination looked unsafe` | HONEST |
| 117 | `it duplicates another result` | HONEST |
| 118 | `it is a different product` | HONEST |
| 119 | `policy refused it` | HONEST |
| 147 | `{n} candidate(s) were hidden.` / `Hidden: {n} because …` | HONEST |
| 225–231 | `{source} was walked through its catalogue instead of being searched… so absence is not evidence of absence.` | HONEST |
| 287 | `Contradictory` | WATCH — entitled idea, missing the word “evidence” |
| 289, 291, 296 | `Incomplete evidence` | HONEST |
| 293 | `High` | **OVERCLAIM** (O2) when used as `authenticity.label` |
| 295 | `Moderate` | WATCH when used as `authenticity.label` |
| 408 | `comparison stage did not run` | HONEST |
| 410 | `no listing images were available to compare` | HONEST |
| 411 | `comparison ran but recorded no compared images` | HONEST |
| 520 | listing_utility `Live` / `Unknown` / `Not live` | HONEST |
| 587 | `Why Real` / `Why Possibly Real` | **OVERCLAIM** (O5) |
| 588 | `This listing met the Real gate under the available evidence.` | HONEST — keep |
| 590 | `The item may match, but important evidence is missing or conflicting.` | HONEST |
| 592 | `Why Replica` | WATCH |
| 593 | `From replica sources. A replica listing can never be ranked Real.` | WATCH |
| 595 | `Reason codes: {codes}` appended to the lead | **OVERCLAIM** (O6) / **USELESS** (U3) |
| 608 | `No physical inspection.` | HONEST / U5 boilerplate |

`why.points`, `why.supporting`, `why.contradictions`, `why.missing`,
and `evidence_chips[].text` are passed through from stored match /
authenticity payloads. They are listing- or measurement-specific
(panel counts, missing views, `ev:` citations). They are not a second
vocabulary of “authentic” / “fake”. Internal tokens such as
`self-declared-replica` or `strong-counterfeit` can appear raw if
they were stored as contradiction strings — same family as O6.

#### Errors and campaign status the UI shows as `detail` / `terminal_reason` / `search.warning`

| File:line | Wording | Verdict |
| --- | --- | --- |
| `src/searcher/api/uploads.py:60` | `Combined upload size exceeds the configured total cap.` | HONEST |
| `src/searcher/api/uploads.py:74` | `A search needs at least one image. The server is the validator.` | HONEST |
| `src/searcher/api/uploads.py:80–81` | `A search can include at most {n} images. The server is the validator.` | HONEST |
| `src/searcher/api/uploads.py:107` | `The upload was rejected.` | HONEST |
| `src/searcher/api/searches.py:32` | `Live re-verification could not import the discovery engine.` | HONEST (“verification” = live-check) |
| `src/searcher/api/searches.py:39` | `No stored listing can be refreshed.` | HONEST |
| `src/searcher/api/searches.py:44` | `Live re-verification did not finish: …` | HONEST |
| `src/searcher/api/searches.py:47–48` | `Availability, price, size, and destination were re-checked where the listing allowed.` | HONEST |
| `src/searcher/api/searches.py:63` | `POST /v1/searches expects multipart/form-data.` | HONEST |
| `src/searcher/api/searches.py:112–114` | refresh unavailable because no published results | HONEST |
| `src/searcher/api/searches.py:118–120` | live re-verification did not run; discovery disabled | HONEST |
| `src/searcher/api/dependencies.py:65, 71` | `This search is no longer available.` | HONEST |
| `src/searcher/api/results.py:29` | `bucket must be real, possibly_real, or replica.` | NEUTRAL |
| `src/searcher/api/results.py:38` / `feedback.py:33` | `This result is no longer available.` | HONEST |
| `src/searcher/api/main.py:93` | `The request did not match the expected fields.` | HONEST |
| `src/searcher/api/capabilities.py:86` | `Retrieval, matching, authenticity, and ranking are not present in this process.` | HONEST (capability, not a verdict) |
| `src/searcher/api/capabilities.py:79` | `The sources/discovery layer is not present in this process.` | HONEST |
| `src/searcher/api/capabilities.py:80` | `Live listing discovery is disabled in this process.` | HONEST |
| `src/searcher/api/capabilities.py:88` | `Result routing is disabled in this process.` | HONEST |
| `src/searcher/workers/api_campaign.py:73–76` | discovery not available; not a finding the item does not exist | HONEST |
| `src/searcher/workers/api_campaign.py:78` | `Live listing search did not run because the discovery layer is not present.` | HONEST |
| `src/searcher/workers/api_campaign.py:110` | `A search can include at most {n} tags.` | HONEST |
| `src/searcher/workers/api_campaign.py:212, 612` | `The server does not have enough storage to keep this search.` | HONEST |
| `src/searcher/workers/api_campaign.py:219, 619, 634` | `The search failed because of an internal error. This is not a no-results outcome.` | HONEST |
| `src/searcher/workers/api_campaign.py:275` | `The search could not use the supplied input.` | HONEST |
| `src/searcher/workers/api_campaign.py:627` | `A supplied image could not be decoded. This is not a no-results outcome.` | HONEST |
| `src/searcher/campaigns/orchestrator.py:245` | routing layer could not be imported | HONEST |
| `src/searcher/campaigns/orchestrator.py:452` | `No admitted sources accepted the compiled queries.` | HONEST |
| `src/searcher/campaigns/orchestrator.py:504` | `Discovery layer is not present.` | HONEST |
| `src/searcher/campaigns/orchestrator.py:754` | `No hypothesis available for retrieval.` | HONEST |
| `src/searcher/campaigns/orchestrator.py:1451` | `budget exhausted` | HONEST |
| `src/searcher/campaigns/orchestrator.py:1466` | `success saturation` | **OVERCLAIM** (O7) |
| `src/searcher/campaigns/orchestrator.py:1468` | `admitted sources were blocked or unavailable` | HONEST |
| `src/searcher/campaigns/orchestrator.py:1472` | `useful coverage remains incomplete; some sources blocked` | HONEST |
| `src/searcher/campaigns/orchestrator.py:1478` | `one or more lanes degraded; results are incomplete` | HONEST |
| `src/searcher/campaigns/orchestrator.py:1489` | `no usable query was compiled` | HONEST |
| `src/searcher/campaigns/orchestrator.py:1491` | `no source work was planned` | HONEST |
| `src/searcher/campaigns/orchestrator.py:1501` | `nothing was fetched` | HONEST |
| `src/searcher/campaigns/orchestrator.py:1502` | `coverage exhausted` | HONEST |
| `src/searcher/campaigns/orchestrator.py:1552` | internal error; not a no-results outcome | HONEST |
| `src/searcher/reference/validation.py` | `path traversal refused`, `empty upload`, `unrecognized or unsupported image magic bytes`, size/dimension refusals | HONEST (shown after `ApiError` strips the class prefix) |

`GET /v1/health` and `GET /v1/capabilities` are not rendered by the
UI (`web/API_EXPECTATIONS.md:254`). Their strings were read; none
assert that an item is authentic.

`POST /v1/results/{id}/feedback` returns `{ ok, feedback_id, receipt_id, applied: false }`
with no claim copy.

Seller title/description are attacker-controlled and inserted as
text (`web/API_EXPECTATIONS.md:207–209`). A seller saying
“100% authentic” is their speech, not Searcher’s. The engine treats
self-declared replica language as a veto; it does not treat a seller
authenticity badge as proof (`SEARCHER_AUTHENTICITY_POLICY.md`).

### G. Development stub (not the product API)

`web/dev/README.md` states the stub is not part of the product and is
not published to Pages. The same `web/` UI will display these strings
if someone runs `python3 web/dev/stub_api.py`. Inventoried so the
surface is not sampled.

| File:line | Wording | Verdict |
| --- | --- | --- |
| `web/dev/fixtures/results/res-real-1.json:30, 36` | item_match / authenticity `High` | **OVERCLAIM** (O2) on authenticity |
| `web/dev/fixtures/results/res-real-1.json:65` | `Why Real` | **OVERCLAIM** (O5) |
| `web/dev/fixtures/results/res-real-1.json:67–71` | `Exact model geometry is strongly consistent.` / `Three independent detail groups agree.` / `No hard authenticity contradiction.` / `Listing is live.` | HONEST (evidence) |
| `web/dev/fixtures/results/res-real-1.json:73–74` | `No physical inspection.` | HONEST |
| `web/dev/fixtures/results/res-real-1.json:123` | `Item match and authenticity evidence both clear the current Real gate, the listing is live, and no hard veto applies.` | HONEST |
| `web/dev/fixtures/results/res-real-2.json:70` | `No hard authenticity contradiction.` | HONEST |
| `web/dev/fixtures/results/res-real-2.json:112` | `Item match and authenticity evidence clear the current Real gate. Sole photography is missing but is not a hard veto under the current benchmark.` | HONEST (does not hide the gap) |
| `web/dev/fixtures/results/res-possible-1.json:36` | authenticity `Incomplete evidence` | HONEST |
| `web/dev/fixtures/results/res-possible-1.json:65` | `Why Possible` | WATCH (same family as O5) |
| `web/dev/fixtures/results/res-possible-1.json:112` | `Item match is plausible, but authenticity-critical views are missing and the photographs are compressed.` | HONEST |
| `web/dev/fixtures/results/res-possible-2.json` | `The pair may be the same model, but size conflicts and the listing is no longer live, so it cannot enter Real.` | HONEST |
| `web/dev/fixtures/results/res-temp-removed.json` | `Will be hidden.` | **USELESS** (dev-only) |
| `web/dev/fixtures/results/res-xss-1.json` / `res-xss-http.json` | Hostile listing strings kept inert; tab_reason says the page is kept only to prove that | HONEST (does not adopt “treat this listing as Real”) |
| `web/dev/fixtures/searches/fixture-normal.json` | `Success saturation: Real results exist…` | **OVERCLAIM** (O7) |
| `web/dev/fixtures/searches/fixture-normal.json` / `fixture-empty-real.json` | `Some candidates did not meet policy.` | **USELESS** (U2) |
| `web/dev/fixtures/searches/fixture-empty-real.json` | `Coverage finished. No candidate cleared the Real gate.` | HONEST |
| `web/dev/fixtures/searches/fixture-empty.json` | `No displayable candidate passed the threshold within the searched sources and budget.` | HONEST |
| `web/dev/fixtures/searches/fixture-blocked.json` | `The campaign could not reach its declared goal because admitted sources were blocked.` | HONEST |
| `web/dev/fixtures/searches/fixture-cancelled.json` | `The search was cancelled before the campaign finished.` | HONEST |
| `web/dev/fixtures/searches/fixture-failed.json` | `An internal error stopped the campaign. This is not a no-results outcome.` | HONEST |
| `web/dev/fixtures/searches/fixture-partial.json` | `Useful results exist, but a major source was blocked and authenticity evidence remains incomplete.` | HONEST |
| `web/dev/fixtures/events/*.json` | progress detail `Reading authenticity evidence on each listing` | HONEST |

`web/dev/stub_api.py` itself has no additional claim slogans; it
replays the fixtures.

---

## Surfaces checked (not sampled)

- [x] `web/index.html` — home, privacy article, limitations article, results drawer, compare dialog, footer
- [x] `web/404.html`, `web/privacy/index.html`, `web/limitations/index.html`
- [x] `web/app.js`, `web/js/api.js`, `web/js/compare.js`, `web/js/dom.js`, `web/js/feedback.js`, `web/js/form.js`, `web/js/format.js`, `web/js/results.js`, `web/js/router.js`, `web/js/scopes.js`, `web/js/storage.js`, `web/config.js`
- [x] `web/README.md`, `web/API_EXPECTATIONS.md`, `web/dev/README.md` — developer-only; no extra product slogans
- [x] Live API projection and errors: `src/searcher/api/{views,uploads,searches,results,feedback,deletion,health,capabilities,main,dependencies}.py`
- [x] Terminal / warning reasons: `src/searcher/workers/api_campaign.py`, `src/searcher/campaigns/orchestrator.py`
- [x] Entitled authenticity labels: `src/searcher/authenticity/{contracts,calibration}.py`
- [x] Stub fixtures under `web/dev/fixtures/{results,searches,events}`
- [x] `styles.css` / `favicon.svg` — no text claims (`100%` there is CSS)

Not a product surface (ceiling only): repo `README.md`, `CLAIMS.md`,
`LIMITATIONS.md`, `SEARCHER_*` policy files.

---

## What the evidence supports saying instead

These replacements are already in the tree’s own voice. They are the
ceiling, restated:

- Real is a list: listings that cleared the current evidence gate.
- Possibly Real is a list: plausible item match, incomplete or
  conflicting evidence.
- Replica, when shown, is a list: self-declared or replica-family
  listings. None of them may sit in Real.
- Authenticity output is an evidence label, never a certificate.
- A finished search may show nothing. That is not “the item does not
  exist” and not “no replica exists”.
- Absence of replica results means replica marketplaces were not
  fetched.

---

## Tests

Command required by the contract:

```text
uv run pytest tests/unit/test_interface_explains_replica_absence.py -q
```

**Blocked on this sparse checkout.** `tests/conftest.py:12` imports
`searcher.campaigns.controller`. `src/` is not materialized, so the
process dies before the test file runs:

```text
ImportError while loading conftest '…/tests/conftest.py'.
ModuleNotFoundError: No module named 'searcher'
```

The four assertions in
`tests/unit/test_interface_explains_replica_absence.py` read only
`web/index.html`. With conftest skipped they pass:

```text
uv run pytest tests/unit/test_interface_explains_replica_absence.py -q --noconftest
....                                                                     [100%]
4 passed in 0.02s
```

Those four checks confirm the honest replica block (O1’s neighbour)
is present: the heading “Why replica sources are not searched”, the
names Taobao / Weidian / Yupoo, “robots”, “never evidence” /
“not evidence”, and “never be ranked Real”. They do not catch O1,
because they do not forbid the earlier false sentence
“Replica sources are searched”.

Widening the sparse-checkout roots to include `src/` would let the
exact required command run.

---

## Risks if nothing changes

- A buyer reads tab **Real** + authenticity **High** + lead
  “exact item” as authentication. The disclaimer is present but is
  competing with shorter, stronger words.
- A buyer reads Limitations line 124, never scrolls, and believes
  replica marketplaces were searched. Empty replica coverage then
  reads as “no replica exists”, which the next paragraph exists to
  prevent.
- `false Real 0` quoted next to the Real definition will be repeated
  as an authenticity accuracy number. `CLAIMS.md` already forbids that.

## Unresolved

- Exact `src/` line numbers are from `git show HEAD:…` at this
  commit. They were not opened as working-tree files.
- Live `why.points` contents are candidate-specific and were not
  exhaustively listed (they are not a second slogan vocabulary).
- Whether a given hard-veto reason code can actually appear on a
  published Real/Possibly Real card is a publication-invariant
  question (`tests/property/test_p16_hard_veto_bars_both_tabs.py`).
  O6 is still a leak in the formatter even if today’s router never
  feeds it those codes.

## Next

Do not edit `web/` or `src/` in this lane. A follow-up that is
allowed to touch those trees should, in order:

1. Delete or rewrite `web/index.html:124` (O1).
2. Stop remapping `HIGH EVIDENCE` → `High` (O2).
3. Split the Limitations definition of Real from the retrieval
   receipt (O3 / U1).
4. Soften the home lead (O4).
5. Stop appending raw reason codes to `tab_reason` (O6 / U3).
6. Replace the leftover “that is all the interface will say” /
   “Some candidates did not meet policy” pair (U2).
