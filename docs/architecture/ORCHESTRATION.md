# Campaign orchestration

The campaign controller is the only writer of campaign state. The
orchestrator in `src/searcher/campaigns/orchestrator.py` asks it to
transition and then calls the engines that already exist.

## Loop

```
reference analysis
→ hypothesis portfolio
→ query portfolio
→ source plan
→ discovery
→ acquisition
→ normalization
→ deduplication
→ broad retrieval
→ fine matching
→ authenticity review
→ live checking
→ ranking
→ publication
→ gap analysis
→ replan or stop
```

Reference through query planning is `run_reference_query_wave`. Everything
after that is the orchestrator. Each stage is optional: if a layer cannot
be imported or a source refuses, that lane is marked blocked and the
campaign continues through what remains.

`COMPLETE` is only allowed with a `SearchExhaustionReceipt`. No matches is
not `FAILED`. A blocked source is never recorded as `SEARCHED_NO_MATCH`.

## Fallback

`SEARCHER_LIVE_DISCOVERY=0` (the API test fixture) keeps the honest
`BLOCKED` stop: reference analysis runs, live listing search does not.
Production `scripts/run_api.sh` sets `SEARCHER_LIVE_DISCOVERY=1`.

## Scripted fixture

The canned offline campaign lives in `src/searcher/fixtures/scripted.py`.
`src/searcher/campaigns/runner.py` is a re-export only. CLI
`campaign create --fixture` still uses that path so crash-resume tests
keep working. A search created through the API never loads it.

## Active loop

After the first publication the orchestrator may promote aliases or
product codes that pass §13.3 contamination controls, compile a new
query round, and discover once more. Seller title alone cannot rewrite
identity.

## Stop

Stop on success saturation, novelty plateau, budget exhaustion, or
coverage exhaustion. The exhaustion receipt records hypotheses, query
families, languages, sources, pages, funnel counts, and the real reason.
