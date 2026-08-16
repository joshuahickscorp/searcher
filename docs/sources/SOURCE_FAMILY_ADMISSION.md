# Source family admission records

Recorded 2026-08-16. New adapters in this wave are **disabled pending
review**. They do not fetch, scrape, or open a new outbound host.

## Newly registered sources

| source_id | family | admission | enabled | domain | open question |
|---|---|---|---|---|---|
| depop | legitimate | review_required | no | www.depop.com | Can robots.txt and terms be fetched without a challenge? |
| grailed | legitimate | review_required | no | www.grailed.com | Can robots.txt and terms be fetched without a challenge? |
| vestiaire | legitimate | review_required | no | www.vestiairecollective.com | Can robots.txt and terms be fetched without a challenge? |
| taobao | replica | review_required | no | www.taobao.com | Is there an admitted item-page path that does not require login? |
| weidian | replica | review_required | no | weidian.com | Is there a fetchable robots.txt and an admitted public listing path? |
| yupoo | replica | review_required | no | yupoo.com | What does robots.txt allow, and is album HTML an admitted listing path? |

SSENSE, eBay, and The RealReal were already registered. They are in the
legitimate family. SSENSE remains `review_required` and disabled.

DHgate is excluded and is not registered.

## Reachable live vs registered-not-enabled

**May be planned when enabled and admitted** (current enabled adapters in
the default planner, legitimate family):

- searx (own instance; `SOURCE_UNAVAILABLE` without `SEARCHER_SEARX_URL`)
- wikimedia
- marginalia
- the_realreal
- rebag
- komehyo
- kind
- byronesque
- heroine
- archive_org
- ebay (`AUTH_REQUIRED` without credentials)
- etsy (`AUTH_REQUIRED` without credentials)

**Registered, family assigned, disabled pending review** (not fetched, not
charged unless a later review enables them):

- Legitimate: vinted, mercari_jp, yahoo_auctions, buyee, bunjang, ssense,
  depop, grailed, vestiaire, farfetch, stockx, goat, poshmark, duckduckgo
- Replica: taobao, weidian, yupoo

A `source_scopes=replica` search currently plans the replica family and
then finds every member disabled. That is an honest empty replica coverage
until review admits a fetch path. It is not a finding that no replica
listing exists.
