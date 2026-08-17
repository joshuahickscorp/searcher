# Listing expansion

An acquired document is classified before it may become a candidate:

- **product** — one item at one URL. This is the only class that becomes a candidate.
- **index** — a collection, search-results page, sitemap, or product feed. Expanded.
- **other** — neither. No candidate.

Indexes are expanded into member product URLs. Those URLs re-enter the existing
frontier as ordinary `listing` work and pass the same admission, robots,
rate-limit, dedup, and budget checks as any other fetch.

Structured feeds are preferred, in order: JSON product feed, JSON-LD `ItemList`,
sitemap `<loc>`, HTML links. A Shopify `products.json` body is read as JSON.
Each product's handle, title, price, and image URLs come from the feed. The
collection URL itself is never stored as a candidate.

Expansion is bounded. `SEARCHER_INDEX_EXPAND_PER_INDEX` (default 24) and
`SEARCHER_INDEX_EXPAND_PER_CAMPAIGN` (default 48) cap how many members are
taken. Every dropped member is counted with a reason
(`per_index_cap`, `per_campaign_cap`, `already_seen`, `host_not_admitted`,
`duplicate_of_index`, `max_depth`, `missing_url`). The counts are written to
an `IndexExpansionReceipt` and to campaign runtime `index_expansions`.

A candidate with no images records `structured_data.images_missing_reason`
instead of failing silently. Feed members with an empty `images` array use
`feed_listed_no_images`. Parsed product pages with none use
`page_extracted_no_images`.

Member URLs on a host that is not the index host or the source manifest domain
are dropped. Page content is data, never instructions.

## Catalogue fallback

When slug-derived collection queries yield nothing, sources that publish a
public catalogue feed page that feed instead of guessing another handle or
touching `/search`. KIND declares `/products.json` (the shop-wide products
JSON, same schema as `/collections/all/products.json`, robots-allowed).
`/search` remains disallowed.

The feed already carries title, brand, handle, price, and image URLs. Query
terms are matched against those fields **in the feed**. Only matching products
are promoted into the frontier. Feed-text matching is a shortlist: it does not
record identity evidence. Existing matching still decides everything after.

Paging is bounded. `SEARCHER_CATALOG_PAGES_PER_SOURCE` (default 64) and
`SEARCHER_CATALOG_PAGES_PER_CAMPAIGN` (default 80) cap pages read.
`SEARCHER_CATALOG_PROMOTE_PER_SOURCE` (default 24) and
`SEARCHER_CATALOG_PROMOTE_PER_CAMPAIGN` (default 48) cap promotions. Every
drop is counted (`feed_text_no_match`, `per_source_page_cap`,
`per_campaign_page_cap`, `per_source_promote_cap`, `per_campaign_promote_cap`,
`already_seen`, `host_not_admitted`, `robots_disallowed`, `missing_url`).
The counts are written to a `CatalogFallbackReceipt` and to campaign runtime
`catalog_fallbacks`. Caps are never applied silently.

The catalogue URL is refused if it matches the source's disallowed prefixes or
`/search`. Rate limits, admission, robots, and the page budget still apply to
each catalogue fetch. A source that publishes no such feed does not take this
path.
