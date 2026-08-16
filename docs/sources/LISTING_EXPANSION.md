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
