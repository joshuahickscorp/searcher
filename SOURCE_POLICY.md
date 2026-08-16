# SOURCE_POLICY

§29.7 per-source rights table. Derived from
`docs/sources/SOURCE_RESEARCH_2026-08-16.md` (fetches of 2026-08-16).
Technical accessibility is not permission.

Honest User-Agent: `Searcher/0.1.0 (+https://github.com/searcher-project/searcher; research-discovery; contact=operators@searcher.invalid)`

| Source | Domain | Access | Admission | Search | Page fetch | Render | Images | Cache | Persistent metadata | Thumbnails | Refresh | Languages | Disallowed / notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SearxNG (own) | operator | self-hosted JSON | admitted | yes | n/a | no | no | yes | yes | no | on-demand | * | Public instances are not the production path. |
| Wikimedia | en.wikipedia.org + sisters | Action API | admitted | yes | yes | no | yes | yes | yes | yes | on-demand | en ja fr it ko zh ru | Honour UA, maxlag, serial requests. |
| Marginalia | api2.marginalia-search.com | API (`public` key) | admitted | yes | no | no | no | yes | yes | no | on-demand | en | CC-BY-NC-SA 4.0 default. Shared key 503s. |
| Internet Archive | archive.org | GET | admitted | yes | yes | no | no | yes | yes | no | never-as-live | en | Disallow `/control/` `/report/`. Historical only. |
| Openverse | api.openverse.org | API | admitted | yes | no | no | yes | yes | yes | yes | on-demand | en | CC identity images, not marketplace listings. |
| The RealReal | therealreal.com | GET item + sitemap | admitted | no | yes | no | no | yes | yes | no | on-demand | en | Stay off `?*before=` `?*after=`. Sitemap-first. |
| Rebag | rebag.com | GET product | admitted | yes | yes | no | no | yes | yes | no | on-demand | en | Disallow `/digital_certificate/`. |
| Komehyo | komehyo.jp | GET product + sitemap | admitted | yes | yes | no | no | yes | yes | no | on-demand | ja en | Open robots. Sitemap-first. |
| KIND | shop.kind.co.jp | GET product/collection | admitted | no | yes | no | no | yes | yes | no | on-demand | ja en | `Disallow: /search`. |
| Byronesque | byronesque.com | GET | admitted | yes | yes | no | no | yes | yes | no | on-demand | en | Disallow `/wp-admin/`. |
| Heroine | shopheroine.com | GET | admitted | yes | yes | no | no | yes | yes | no | on-demand | en | Empty Disallow. Storefront identity is an open question. |
| eBay | api.ebay.com | Browse API only | admitted (API) | yes (API) | yes (API) | no | no | no | yes | no | API TTL | en | Web `/sch/` forbidden. Adapter reports `AUTH_REQUIRED` without a key. |
| Etsy | api.etsy.com | Open API v3 only | admitted (API) | yes (API) | yes (API) | no | no | no | yes | no | 6h listings | en | Screen-scraping forbidden. `AUTH_REQUIRED` without a key. |
| Vinted | vinted.com | GET items | review_required | no | yes | no | no | no | yes | no | on-demand | en fr de it | `Content-Signal: search=yes, ai-train=no`. Disabled by default. |
| Mercari JP | jp.mercari.com | GET item | review_required | no | yes | no | no | yes | yes | no | on-demand | ja | Never `/v1/` `/v2/`. Disabled; ToS unverified. |
| Yahoo Auctions | auctions.yahoo.co.jp | GET item | review_required | no | yes | no | no | yes | yes | no | on-demand | ja | Never `/closedsearch`. Disabled. |
| Buyee | buyee.jp | GET public catalog | review_required | no | yes | no | no | yes | yes | no | on-demand | ja en | Link only, never bid. No `/api/v1/` `/internalapi/`. Disabled. |
| Bunjang | m.bunjang.co.kr | GET public | review_required | no | yes | no | no | yes | yes | no | on-demand | ko | Disabled; JS completeness unverified. |
| SSENSE / Farfetch / StockX / GOAT / Poshmark | various | GET product | review_required | no | yes | no | no | yes | yes | no | on-demand | en | Search URLs disallowed. Disabled by default. |
| DuckDuckGo HTML | html.duckduckgo.com | GET | review_required | yes | no | no | no | no | no | no | transient | en | ToS unverified. Disabled. |
| Grailed / Vestiaire / Depop | — | — | blocked | no | no | no | no | no | no | no | — | — | Cloudflare interstitials on robots/terms 2026-08-16. |
| ZOZO / 2nd Street / RAGTAG / Weidian / 1688 | — | — | blocked | no | no | no | no | no | no | no | — | — | robots fetch failed or explicitly disallows generic automation. |
| Serper / SerpAPI | — | — | out of scope | no | no | no | no | no | no | no | — | — | Human decision pending; they scrape Google. |

A refusal (robots, terms, 401/403/429/challenge) is recorded as the matching
`SourceOutcome` and is never collapsed into `SEARCHED_NO_MATCH`.
