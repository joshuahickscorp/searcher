I'll gather primary sources first: `robots.txt`, official API docs, and terms for every candidate, then rank what Searcher can admit without bypassing access control.I'll pull the project's existing source-policy notes next, then fetch `robots.txt` and official API/terms pages in parallel.Brave’s terms are in hand. Next I’ll fetch marketplace `robots.txt` files and official API/terms pages so each source can be classified from primary text.eBay and Vinted `robots.txt` are in. Next I’ll pull the remaining marketplace files plus official API and terms pages.Western `robots.txt` files are in. Next I’ll fetch Japanese, Korean, and Chinese storefronts plus official API and terms pages.I have API and robots coverage for the main search and marketplace set. Next I’ll pull the remaining official API/terms pages, archival fashion sites, and legal sources.I have the primary `robots.txt`, API, and terms evidence needed. The report below is the research deliverable.

# Searcher source-research report

**Date of fetches:** 2026-08-16  
**Scope:** public pages and documentation only. No accounts, no CAPTCHA solving, no workarounds. A source that cannot be reached without those is **not admitted**.

**Status vocabulary used below**

| Status | Meaning |
|---|---|
| `admitted` | A documented, legitimate access path exists that does not require bypassing a gate. |
| `blocked` | Fetch failed behind bot/region/auth control, or robots/terms forbid the intended use. Record as blocked, never as empty results. |
| `review_required` | Primary text is mixed, the official API exists but needs a human contract/key decision, or robots allow crawl while terms forbid automated access. |

---

## 1. Recommended launch source set (ranked)

This table is written to become `SOURCE_POLICY.md`. Rank is “search this first for a rare garment,” not “easiest to scrape.”

| Rank | Source | Class | Access method | Credential | Status | Basis | Expected fields | Sold-state | Rate |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Self-hosted SearxNG** | metasearch | Local `/search?q=&format=json` | none (self-host) | `admitted` for **own** instance | Official Search API: JSON is a first-class format if enabled in `settings.yml`. Public instances must not be the production path. [docs.searxng.org/dev/search_api.html](https://docs.searxng.org/dev/search_api.html) 2026-08-16: “Be aware that many public instances have these formats disabled.” [docs.searxng.org/own-instance.html](https://docs.searxng.org/own-instance.html): public instances “may cause the external service to enforce CAPTCHAs or to ban the IP.” | title, url, snippet, engine, optional thumbnail | n/a (aggregator) | Operator-set; upstream engines will independently 429/CAPTCHA. If an engine CAPTCHAs, mark that engine `blocked`. |
| 2 | **Wikimedia / Wikipedia Action API** | reference / identity | `https://en.wikipedia.org/w/api.php` (and sister wikis: ja, fr, it, ko, zh, ru) | none | `admitted` | [foundation.wikimedia.org Policy:Wikimedia Foundation API Usage Guidelines](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_API_Usage_Guidelines) v1.0 2024-08-26: community members need no prior permission if they follow UA, rate limits, licenses. [mediawiki.org/wiki/API:Etiquette](https://www.mediawiki.org/wiki/API:Etiquette): descriptive User-Agent with contact; serial requests; `maxlag`. Article HTML is crawlable: `User-agent: *` allows `/wiki/` except Special: and talk/admin paths. [en.wikipedia.org/robots.txt](https://en.wikipedia.org/robots.txt) 2026-08-16. | title, extract, images, langlinks, categories, sitelinks. Identity aliases (ディオールオム, Dior Homme, etc.). | n/a | Soft; honor 429/`ratelimited` and `maxlag`. Do not fan out in parallel. |
| 3 | **Marginalia Search API** | independent web index | `GET https://api2.marginalia-search.com/search?query=` | header `API-Key: <REDACTED> works with no signup | `admitted` (non-commercial default) | [about.marginalia-search.com/article/api/](https://about.marginalia-search.com/article/api/) updated 2025-12-08: “If you want to develop an integration but do not yet have a key, you can use the key `public`.” Default license **CC-BY-NC-SA 4.0**. Commercial key is a paid product. | url, title, description, license | n/a | Shared `public` key “often hits a rate limit” → HTTP 503. Email for a free non-commercial key. Niche/old-web bias: useful for blogs/lookbooks, weak for live listings. |
| 4 | **Internet Archive** | archival / sold history | `archive.org` web pages + Wayback | none | `admitted` | [archive.org/robots.txt](https://archive.org/robots.txt) 2026-08-16: `User-agent: *` Disallow only `/control/` and `/report/`. | historical listing HTML, capture date | 404/tombstone of live site vs archived “ended” page | Polite; IA is a public archive, not a live marketplace. |
| 5 | **Common Crawl (offline)** | offline web corpus | S3 WARC / CDXJ / Athena; **not** a live query | none for the dataset | `admitted` as **offline index only** | [commoncrawl.org/faq](https://commoncrawl.org/faq) 2026-08-16: “no cost for the purpose of research and analysis.” [commoncrawl.org/terms-of-use/](https://commoncrawl.org/terms-of-use/) last updated 2024-03-07: Crawled Content “may be subject to separate terms… from the owners”; user must “RESPECT THE COPYRIGHTS… OF THIRD PARTIES”; indemnity for AI-system use. CDX live API is heavily rate-limited; FAQ: “don't use proxy networks.” | url, timestamp, html/warc payload if the page was crawled | snapshot age only | Bulk via S3/Athena. `index.commoncrawl.org` 503s under load. Treat CC pages as stale evidence, never as a live listing. |
| 6 | **DuckDuckGo HTML** | general web (zero-key) | `html.duckduckgo.com` | none | `review_required` | [html.duckduckgo.com/robots.txt](https://html.duckduckgo.com/robots.txt) 2026-08-16: `User-agent: *` `Allow: /`. No official JSON API. DDG ToS for automated commercial reuse **unverified** on this pass (page not fetched). Use only as a SearxNG engine or very low-rate HTML search until ToS are read. | title, url, snippet | n/a | Unverified official rate. Stop on 429/CAPTCHA and mark blocked. |
| 7 | **Openverse** | CC image index | `https://api.openverse.org/v1/` | none for a low tier; OAuth for “standard” | `admitted` for CC images | [docs.openverse.org](https://docs.openverse.org/api/reference/authentication_and_throttling.html): unauthenticated throttle exists; registering an application unlocks `standard`. Images are openly licensed. Use for lookbook/editorial identity, not marketplace listings. | image url, source, license, title | n/a | Anonymous throttle; register for more. |
| 8 | **eBay Browse API** | Western resale | Official REST `item_summary/search`, `searchByImage`, `getItem` | eBay Developers keyset (OAuth) | `admitted` **API only** | [developer.ebay.com/develop/api/buy/browse_api](https://developer.ebay.com/develop/api/buy/browse_api) (index via search 2026-08-16): keyword, GTIN, category, **image** search. [developer.ebay.com/develop/get-started/api-call-limits](https://developer.ebay.com/develop/get-started/api-call-limits): Browse API default **5,000 calls/day** (except `getItems` also 5,000). [ebay.com/robots.txt](https://www.ebay.com/robots.txt) v29_COM_July_2026: “The use of robots or other automated means to access the eBay site without the express permission of eBay is strictly prohibited” except “publicly available search engines”; “Approved enterprise integrations must use our official API.” `Disallow: /sch/` and `Disallow: /sch/i.html?_nkw=` for `User-agent: *`. **Web search is not admissible.** Developer HTML pages themselves returned eBay “Something went wrong” from this host — API docs exist; signup is a human step. | title, price, currency, condition, buyingOptions, itemEndDate, image, itemWebUrl, seller, category, localized aspects | API: `itemEndDate`, `buyingOptions` empty / ended. Web `/itm/{id}` liveness **unverified** here (do not scrape search). | 5,000/day default; Growth Check for more. Do not circumvent. |
| 9 | **The RealReal** | consignment | GET product / designer / shop pages | none | `admitted` for **item pages and sitemap**; search pagination restricted | [therealreal.com/robots.txt](https://www.therealreal.com/robots.txt) 2026-08-16: Disallow cart/checkout/login/admin/consign; Disallow `?*before=` and `?*after=` on shop/designers/products. Sitemap: `https://www.therealreal.com/sitemaps/sitemap_index.xml`. No public product API found. | title, designer, price, condition, images, description — **JSON-LD unverified** (listing HTML not fetched) | unverified (expect 404 or “sold” copy on PDP) | No crawl-delay. Stay off paginated `before`/`after` URLs. Prefer sitemap + known product URLs from web search. |
| 10 | **Rebag** | luxury resale | GET product pages | none | `admitted` | [rebag.com/robots.txt](https://www.rebag.com/robots.txt) 2026-08-16: `User-Agent: *` `Disallow:` (empty) plus `/digital_certificate/`. Sitemap listed. Homepage redirected to a marketing shop URL — product-page HTML/JSON-LD **unverified**. | title, brand, price, condition, SKU — unverified | unverified | No delay stated. |
| 11 | **Komehyo** | JP official consignment | GET product pages | none | `admitted` | [komehyo.jp/robots.txt](https://komehyo.jp/robots.txt) 2026-08-16: `User-agent: *` and two sitemaps only. No Disallow. High-value JP authenticated-goods source. | brand, model, grade, price, images — JSON-LD **unverified** | unverified | No delay. Sitemap-first. |
| 12 | **KIND / Kindal** (`shop.kind.co.jp`) | JP archive / 古着 | GET `/products/*` and `/collections/*` | none | `admitted` for product/collection; **not** `/search` | [shop.kind.co.jp/robots.txt](https://shop.kind.co.jp/robots.txt) 2026-08-16 (Shopify): `Disallow: /search`. Product pages allowed except variant/remote junk. `Nutch` Disallow `/`. | Shopify Product JSON-LD is typical; **unverified on a live PDP**. Title, price, vendor, tags (often 中古/古着). | sold items usually 404 or “sold out” on Shopify — unverified | No delay for `*`. Do not hit `/search`. Discover via collections + web search. |
| 13 | **Byronesque** | archival designer | GET WordPress pages | none | `admitted` | [byronesque.com/robots.txt](https://byronesque.com/robots.txt) 2026-08-16: Disallow `/wp-admin/` only; sitemap `sitemap_index.xml`. | title, price, description, images — JSON-LD **unverified** | unverified | No delay. |
| 14 | **Heroine** (`shopheroine.com`) | archival designer | GET pages | none | `admitted` | [shopheroine.com/robots.txt](https://shopheroine.com/robots.txt) 2026-08-16: `User-agent: *` `Disallow:` (empty). Confirm this is the intended “Heroine” storefront before launch — name collision risk. | unverified | unverified | No delay. |
| 15 | **Vinted** | C2C Europe | GET listing pages | none | `review_required` | [vinted.com/robots.txt](https://www.vinted.com/robots.txt) 2026-08-16: `Content-Signal: ai-train=no, search=yes, ai-input=yes` for `User-agent: *`. “AI systems may crawl and index publicly available pages **for search and discovery purposes only**.” Transactional bots forbidden. GPTBot/CCBot etc. Disallow `/`. Searcher-as-search is the use they grant; storing full listing bodies and training on them is reserved. | title, price, size, brand, photos — JSON-LD **unverified** | unverified (often “sold” badge, URL persists) | No crawl-delay. Honor Content-Signal. Prefer item URLs from an admitted search API, not unbounded crawl. |
| 16 | **Mercari Japan** | JP C2C | GET item pages | none for public items | `review_required` | [jp.mercari.com/robots.txt](https://jp.mercari.com/robots.txt) 2026-08-16: Disallow `/mypage/`, `/purchase/`, `/sell/`, `/transaction/`, `/v1/`, `/v2/`. Item and search paths not disallowed. No official public search API found. Terms of automated access **unverified** (ToS page not fetched). | title, price, status, brand, photos. Searcher already sees 中古 in public SERP snippets. | commonly a sold badge on a still-200 page — **unverified on HTML** | No delay. Do not touch `/v1/` `/v2/` (app APIs). If JS-only or app-gated, mark blocked. |
| 17 | **Yahoo! Auctions Japan** | JP auction | GET item pages | none for public item HTML | `review_required` | [auctions.yahoo.co.jp/robots.txt](https://auctions.yahoo.co.jp/robots.txt) 2026-08-16: Disallow members/sell/user/watchlists; Disallow `/search/*?*` extra filters; Disallow `/closedsearch`. Basic `/search/` without those params is not globally disallowed. Official auction API URL `developer.yahoo.co.jp/webapi/auctions/` **404** on 2026-08-16 — no current public API. | title, current price, end time, condition, photos — JSON-LD **unverified** | closed lots: do not use `/closedsearch`. Live item URL → ended copy or redirect — unverified | No delay. Prefer item IDs discovered via Buyee/web search. |
| 18 | **Buyee** | JP proxy storefront (link only) | GET public item/search HTML | none | `review_required` | [buyee.jp/robots.txt](https://buyee.jp/robots.txt) 2026-08-16: Disallow account/order/api/internal; Disallow `/mercari/item/description/`. Public catalog not disallowed. [buyee.jp/helpcenter/guide/caution](https://buyee.jp/helpcenter/guide/caution): Buyee does not authenticate goods; “the customer bears full responsibility.” Searcher **links only, never bids**. Full Terms of Use beyond this caution page **unverified**. | Yahoo/Mercari title, JPY price, photos, source marketplace | auction ended / item gone — unverified | No delay. Do not hit `/api/v1/` or `/internalapi/`. |
| 19 | **Bunjang** | KR C2C | GET public pages | none | `review_required` | [m.bunjang.co.kr/robots.txt](https://m.bunjang.co.kr/robots.txt) 2026-08-16: `User-agent: *` Allow `/` except login/apps/talk. Training bots Disallow `/`; search bots Allow. Sitemaps present. App-centric UX; whether a listing is complete without JS **unverified**. | title, price, region — unverified | unverified | No delay for `*`. |
| 20 | **Etsy Open API v3** | handmade / vintage | Official API | app key + OAuth | `admitted` **API only** | [developers.etsy.com/documentation](https://developers.etsy.com/documentation) 2026-08-16: “Applications must not sidestep the API… Screen-scraping is not allowed.” Caching: listings ≤ 6 hours, other content ≤ 24 hours (quoted via [etsy.com/legal/api](https://www.etsy.com/legal/api/) search excerpt 2026-08-16; full legal page required JS and was not readable). [etsy.com/robots.txt](https://www.etsy.com/robots.txt): `Disallow: /search?*q=`. Web keyword search is not admissible. | listing title, price, url, images, taxonomy, when/state | API state / sold listing | Third-party quotes 10k/day, 10 rps — **unverified** on Etsy primary HTML. Follow official headers. |
| 21 | **SSENSE** | retail / archive drop | GET product pages | none | `review_required` | [ssense.com/robots.txt](https://www.ssense.com/robots.txt) 2026-08-16: `Disallow: /*?q=*`, `/*?page=*`, `/api/`. Product paths not disallowed. No public API found. | designer, description, SKU, price, images — JSON-LD **unverified** | 404 or sold-out — unverified | No delay. Discover via sitemap + web search, never `?q=`. |
| 22 | **Farfetch** | retail aggregator | GET product pages | none | `review_required` | [farfetch.com/robots.txt](https://www.farfetch.com/robots.txt) 2026-08-16: `Disallow: */search` and `*/search/`. Product pages not globally disallowed. | designer, price, size, images — unverified | unverified | No delay. No `/search`. |
| 23 | **StockX** | sneaker/resale | GET product pages | none | `review_required` | [stockx.com/robots.txt](https://stockx.com/robots.txt) 2026-08-16: `Disallow: */search*`, `/api/`, `/listings`. Product pages not disallowed. Heavy bot wall historically — **live HTML unverified**. | style code, market price, images | last sale / “sold out” is JS-heavy — unverified | No delay stated. If a GET is challenged, mark `blocked`. |
| 24 | **GOAT** | sneaker/resale | GET product pages | none | `review_required` | [goat.com/robots.txt](https://www.goat.com/robots.txt) 2026-08-16: `Disallow: /search`, `/new-search*`. Allows `/web-api/consumer-search/*` but then Disallow `*?query=` — do **not** treat the web-api path as a public API. | style, price, images | unverified | Same as StockX. |
| 25 | **Poshmark** | C2C US | GET individual listing pages | none | `review_required` | [poshmark.com/robots.txt](https://poshmark.com/robots.txt) 2026-08-16: `Disallow: /search`, `/listings`, `/api`. Individual `/listing/...` not generally disallowed (share/like/buy are). | title, price, size | sold closet badge — unverified | No delay except Pinterestbot. |
| 26 | **Rakuten Ichiba** | JP retail | GET shop/item pages | none | `review_required` | [rakuten.co.jp/robots.txt](https://www.rakuten.co.jp/robots.txt) 2026-08-16: Disallow `/shops/`, `/com/`, `/images/`. Item HTML paths not fully mapped. No public search API confirmed. | title, shop, price | unverified | Unverified. |
| 27 | **Rakuma / Fril** | JP C2C | GET item pages | none | `review_required` | [item.fril.jp/robots.txt](https://item.fril.jp/robots.txt) 2026-08-16: `Disallow: /search/` with `Allow: /search/$`. Facet querystrings disallowed. Item pages not disallowed. | title, price, 中古 | unverified | No delay. |
| 28 | **Goofish / Xianyu** | CN C2C | GET public pages | none | `review_required` | [goofish.com/robots.txt](https://www.goofish.com/robots.txt) 2026-08-16: only account playground paths disallowed. Whether listings render without app/login **unverified**. Region/login walls common — if challenged, `blocked`. | unverified | unverified | Unverified. |
| 29 | **Taobao** | CN retail | GET `/list/*` only | none | `review_required` / likely **not useful** | [taobao.com/robots.txt](https://www.taobao.com/robots.txt) 2026-08-16: `Allow: /list/*` and `/list/*?*`; `Disallow: /*?*`; `Allow: /$`. Item detail URLs typically have query strings → disallowed. Login/app wall expected. | list cards only | n/a | If item pages require login, `blocked`. |
| 30 | **Brave Search API** | general web + images | Official API | **key + card** | `admitted` once a key exists | [brave.com/search/api/](https://brave.com/search/api/) and [api-dashboard.search.brave.com/documentation/pricing](https://api-dashboard.search.brave.com/documentation/pricing) 2026-08-16: $5/1k Search requests; **$5 free credit / month**; 50 qps. Image endpoint exists. [Terms 11 Feb 2026](https://api-dashboard.search.brave.com/documentation/resources/terms-of-service) §3.2: “shall not… (i) store, cache, or create a database of Search Results… other than transient storage”; (xiii) no training; (xii) no redistribute/resell results. FAQ: storage rights need a special plan. Independent index, not a Google scrape. | web url/title/snippet; image thumbnail+source url | n/a | 50 qps Search. Transient cache only unless a storage-rights plan is bought. |
| 31 | **Poizon / Dewu web** | CN authenticated resale | GET product pages | none | `review_required` | [poizon.com/robots.txt](https://www.poizon.com/robots.txt) 2026-08-16: `Disallow: /search`. Product paths not disallowed. Baiduspider Disallow `/`. App-first. | style code, auth photos | unverified | No delay. No `/search`. |
| 32 | **1688** | CN wholesale | — | — | `blocked` for Googlebot-class / generic automation | [1688.com/robots.txt](https://www.1688.com/robots.txt) 2026-08-16: `User-agent: Googlebot` `Disallow: /` then limited Allows. `User-agent: *` Disallow `/*?*`. Not a legitimate Western search path. | — | — | — |

**Not in the ranked set because they failed this research pass**

| Source | Status | Why |
|---|---|---|
| Grailed | `blocked` | [grailed.com/robots.txt](https://www.grailed.com/robots.txt) and `/legal/terms` returned Cloudflare “Sorry, you have been blocked” (Ray `a2bdc3c38f1e46f9`, `a2bdc87b38a83282`) on 2026-08-16. |
| Vestiaire Collective | `blocked` | robots.txt and terms returned Cloudflare interstitial (“Just a moment…”) on 2026-08-16. |
| Depop | `blocked` | robots.txt returned bot-check interstitial (Ray `a2bdc3c41d6ca2ce`) on 2026-08-16. |
| ZOZOTOWN | `blocked` | `zozo.jp/robots.txt` and `www.zozo.jp/robots.txt` failed HTTP on 2026-08-16. |
| 2nd Street | `blocked` | `www.2ndstreet.jp/robots.txt` → Akamai Access Denied (`errors.edgesuite.net`) on 2026-08-16. |
| RAGTAG | `blocked` | `www.ragtag.jp/robots.txt` request failed on 2026-08-16. Public SERP shows the brand index exists (e.g. Dior Homme ディオールオム). |
| Weidian | `blocked` | `weidian.com/robots.txt` redirected to `h5.weidian.com/m/abnormal/404.html`. |
| KREAM / Cream | `blocked` / unverified | `kream.co.kr/robots.txt` returned empty body. `kindal.jp` DNS NXDOMAIN (real store is `shop.kind.co.jp`). |
| Google Custom Search JSON API | `blocked` for new apps | [developers.google.com/custom-search/v1/overview](https://developers.google.com/custom-search/v1/overview) last updated 2026-02-18: “The Custom Search JSON API is closed to new customers… Existing… until **January 1, 2027**.” |
| Bing Web Search API v7 | `blocked` (retired) | [learn.microsoft.com/lifecycle/announcements/bing-search-api-retirement](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement) 2025-05-15: retired **11 August 2025**. Replacement is Azure “Grounding with Bing,” an LLM-grounding product, not a general search API. |
| SerpAPI / Serper | `review_required` | Documented commercial APIs that return Google SERPs. They are not Google’s API. Human must decide whether buying a Google-scrape vendor violates Searcher’s “no bypass” rule. Details in §A. |
| TinEye | `admitted` after paid key | Reverse-image, commercial only. [tineye.com/legal](https://tineye.com/legal) (search excerpt 2026-08-16): “TinEye is free for non-commercial use only. If you wish to use TinEye commercially, you must purchase access to the commercial TinEye API.” [services.tineye.com/TinEyeAPI](https://services.tineye.com/TinEyeAPI): Starter $200 / 5,000 searches. No free commercial tier. Full legal HTML did not render in the fetch. |

---

## 2. The zero-credential path

### Day one, no API keys, no sign-ups

A self-hosted Searcher can lawfully do all of the following:

1. **Run its own SearxNG** and query it as `GET /search?q=…&format=json` (enable `json` locally). This is the sanest **zero-credential default** for a self-hosted engine: one process, many upstream engines, no third-party instance trust.  
   - Do **not** depend on public SearxNG instances. Official docs: you must trust the operator; abuse of public instances causes upstream CAPTCHAs/IP bans ([docs.searxng.org/own-instance.html](https://docs.searxng.org/own-instance.html), 2026-08-16).  
   - SearxNG “generat[es] a random browser profile for every request” to upstream engines. That is *their* software; Searcher must still treat an upstream CAPTCHA/ban as **blocked**, not as a prompt to rotate anything.  
   - Prefer engines inside SearxNG that are themselves admitted (DuckDuckGo, Wikipedia, Marginalia, Brave-if-keyed). Disable engines that require scraping a `Disallow` path.

2. **Call Marginalia** with `API-Key: <REDACTED> — the only general web JSON API that is documented to work with a published public token and no signup ([about.marginalia-search.com/article/api/](https://about.marginalia-search.com/article/api/), 2025-12-08). License is CC-BY-NC-SA 4.0 unless a commercial key is bought. Shared rate limit → 503 is expected. Good for blogs, lookbooks, personal archives; bad as a live marketplace index.

3. **Call Wikimedia Action API** with a contactable User-Agent. Zero key. This is the identity/alias backbone (Dior Homme ↔ ディオールオム ↔ 디올 옴므, season pages, lookbook citations).

4. **Read Internet Archive** captures of listings that web search already found. robots.txt allows it.

5. **Read Common Crawl WARCs offline** (S3, no live hammering of `index.commoncrawl.org`). Use for historical aliases and hard negatives, never as “this is for sale now.”

6. **GET individual product URLs** that (a) were discovered by an admitted search path and (b) are not `Disallow`ed: RealReal product URLs, Rebag, Komehyo, KIND products, Byronesque, Heroine, Vinted items, Mercari items, Yahoo auction items, Buyee public items, SSENSE/Farfetch/StockX/GOAT product URLs (not their `/search`). If any of those GETs returns a challenge page, record **blocked**.

7. **Openverse** unauthenticated, for CC lookbook/editorial images only.

**What day-one cannot do well:** live eBay/Etsy keyword search, Google-quality web ranking, reverse-image over the commercial web, Grailed/Vestiaire/Depop, ZOZO, Weidian item search, Taobao item detail.

### What each later key buys

| Key | What it unlocks | What it does **not** unlock |
|---|---|---|
| **Brave Search** (`X-Subscription-Token`) | Independent web + **image** search; ~1,000 queries/month on the $5 credit; 50 qps. Sanest **first paid** key. | Persistent result database (ToS §3.2(i), 11 Feb 2026) unless a storage-rights plan is purchased. Training. Redistribution of results. |
| **eBay Developers keyset** | The only legitimate eBay search, including `searchByImage`. 5,000 Browse calls/day. Item liveness via `getItem`. | Scraping `/sch/` or `/itm` search facets. robots.txt and the API License Agreement both point automation at the API. |
| **Etsy app key + OAuth** | Legitimate listing search. Required if Etsy is in the public UI. | Scraping etsy.com (explicitly forbidden). Cache older than 6 hours for listings. |
| **Marginalia personal/commercial key** | Private rate limit; custom XML domain filters (include JP consignment domains, exclude junk). Commercial key drops NC-SA. | A fashion-specific index. Still a small independent crawl. |
| **Openverse OAuth** | Higher image-search throttle on CC content. | Marketplace photos (those are not CC). |
| **TinEye commercial** | True reverse-image over TinEye’s web index. Best legitimate image-identity tool after Brave Images. | Free commercial use. Semantic “similar style” search (it is near-duplicate, not CLIP). |
| **Serper** | Google SERP JSON. Homepage 2026-08-16: “2,500 free queries,” “No credit card required,” from $0.30/1k. [serper.dev/terms](https://serper.dev/terms) 2024-05-29: “web-scraped data collected from public domain sources”; “not affiliated with or endorsed by Google.” | A Google license. **Human decision:** is paying a Google-scraper “bypassing access control”? Default recommendation: **do not admit** until counsel says yes. |
| **SerpAPI** | Broader engine coverage (Google, Bing, Yahoo, Baidu, Yandex). [serpapi.com/pricing](https://serpapi.com/pricing) 2026-08-16: Starter $25 / 1,000 searches; [serpapi.com/legal](https://serpapi.com/legal) 2026-04-08 §13 “U.S. Legal Shield” for paid tiers — they assume scraping liability, which is the tell. | Same policy problem as Serper. Also Reddit-related litigation is in the public record (not fetched as a primary case file here). |

**Sanest default stack:** self-hosted SearxNG (DDG + Wikipedia + Marginalia engines) → Wikimedia API → admitted product-URL GETs. First key: **Brave**. Second: **eBay Browse**. Third: **TinEye** if image identity is weak. Do not start with SerpAPI/Serper.

---

## 3. International / replica lane

### International sources Searcher may use

**Publicly fetchable (item page, no account), with the caveats in the table:** Komehyo, KIND, Byronesque, Heroine, Mercari JP item pages, Yahoo Auctions item pages, Buyee public pages, Rakuma item pages, Vinted items, Bunjang public pages, Goofish (if the GET is 200 HTML).

**Requires an account to do anything useful:** most Taobao item pages, Weidian (robots 404’d), 1688, Poizon app features, Mercari purchase/chat, Yahoo bidding (Yahoo Premium / JP identity). Searcher does not transact, so “requires account to buy” is fine; “requires account to **see** the listing” is `blocked`.

**Requires an app:** Poizon/Dewu core catalog, much of Xianyu, much of Weidian, Cream/KREAM. If the public web page is an empty shell, `blocked`.

**Proxy/agent services (link only):** Buyee is the only one whose robots.txt and a public caution page were successfully read. FromJapan, ZenMarket, Superbuy, CSSBuy, CNFans, Pandabuy — **unverified** this pass (pages not fetched). Policy for all of them: Searcher may link a **public** catalog URL the same way it links eBay. It must not create accounts, bid, or scrape authenticated dashboards. If the public catalog GET is challenged, `blocked`.

Buyee’s own caution page is useful as an authenticity hard-negative: “Our inspection does not cover checking the authenticity of goods” ([buyee.jp/helpcenter/guide/caution](https://buyee.jp/helpcenter/guide/caution), 2026-08-16).

### Replica-web reality (identity + hard negatives only)

How replica inventory is **publicly** surfaced, without any evasion advice:

- **Yupoo albums** — image catalogs. Public web search for `yupoo` + model name is how they are found. Yupoo is a photo host, not a checkout.
- **Weidian / Taobao item IDs** — numeric IDs pasted in forums and agent UIs. Weidian’s robots endpoint was a 404; treat Weidian as `blocked` until a public HTML item URL loads without login.
- **Agent storefronts** (Superbuy, CSSBuy, CNFans, etc.) — they re-host a Weidian/Taobao ID as a public-looking card. If that card is a public URL and robots allow it, Searcher may **link** it as evidence. If it is login-only, skip.
- **Forum/Reddit/Discord indexes** — “W2C” posts. Reddit’s terms and robots are hostile to scraping; do not scrape Reddit. If a Brave/SearxNG result already quotes a public page, use that snippet.

**Vocabulary the query compiler needs** (public seller language; self-declared replica → internal reject, never Real / Possibly Real):

| Token | Role |
|---|---|
| `QC`, `QC pics`, `QC photo` | Quality-control photos of a replica unit |
| `W2C`, `where to cop` | Link to the seller/album |
| `1:1`, `AAA`, `AAA+`, `retail`, `retail batch` | Grade claims |
| `budget`, `mid-tier`, `top`, `best batch` | Price/quality tier |
| `PK`, `PK 4.0`, `LJR`, `GX`, `M batch`, `OG batch`, `H12`, `S2`, `KW`, `Coco`, `Godkiller` | Factory / batch aliases (sneakers especially) |
| `factory`, `batch`, `updated batch` | Versioning |
| `reps`, `replica`, `rep`, `mirror`, `clone` | English self-ID |
| `高仿`, `复刻`, `精仿`, `原单`, `莆田` | zh self-ID / origin |
| `スーパーコピー`, `レプリカ` | ja self-ID |
| `레플리카`, `가품`, `미러급` | ko self-ID |
| Weidian/Taobao numeric ID | cross-post identifier |
| Yupoo album URL | image identity source |

**Legitimate search method:** run those tokens as **negative filters** on the Real/Possibly Real compilers, and as **positive filters** on an internal reject/hard-negative lane, using only admitted search APIs (Brave, SearxNG/DDG, Marginalia) and robots-allowed pages. Do not log into Yupoo/Weidian. Do not solve their gates. A self-declared replica listing is evidence of aliases and of what a fake looks like, then it is discarded from public tabs.

**Blocked on this lane:** any replica site that only exists behind an app, login, invite Discord, or CAPTCHA. That is the expected outcome.

---

## 4. Multilingual query term tables

Brand and model **names stay in Latin** on every market (`Dior Homme`, `General Army Trainer`, `Hedi Slimane`). Also emit the local script form — that is what JP/KR/CN sellers actually type.

Flagship working example: **Dior Homme General Army Trainer 07**.

### 4.1 Brand / house / model

| Lang | Brand as sellers write it | Model / garment | Notes |
|---|---|---|---|
| **en** | `Dior Homme` `Dior Homme 07` `DH` `Hedi` `Hedi Slimane` | `General Army Trainer` `Army Trainer` `trainer` `sneaker` | Keep `Dior Homme` untranslated. |
| **ja** | `ディオールオム` `ディオール オム` `DIOR HOMME` `ディオール・オム` | `トレーナー` `スニーカー` `アーミートレーナー` `ジェネラル` | Verified live SERP/shop copy 2026-08-16: Rakuten, Mercari, Yahoo Auctions, KIND, RAGTAG, 2nd Street, Fril all use **ディオールオム / ディオール オム** next to Latin `Dior Homme` ([search.rakuten.co.jp](https://search.rakuten.co.jp/search/mall/ブランド+トレーナー/551177/tg1013285/), [jp.mercari.com](https://jp.mercari.com/s/172479), [auctions.yahoo.co.jp](https://auctions.yahoo.co.jp/search/search/%28ディオールオム%20diorhomme%29/23000/), [shop.kind.co.jp](https://shop.kind.co.jp/collections/dior-homme/), [ragtag.jp/brand/20100](https://www.ragtag.jp/brand/20100/)). Do **not** translate to 男性向けディオール. |
| **ko** | `디올 옴므` `디올옴므` `Dior Homme` | `스니커즈` `트레이너` `아마이 트레이너` | Hangul brand is used; Latin still matches. **Unverified** on a live Bunjang HTML page this pass. |
| **zh-Hans** | `迪奥` `迪奥·桀傲` `Dior Homme` `迪奥男士` | `运动鞋` `训练鞋` `Army Trainer` kept Latin | Luxury CN often keeps French model names. `桀傲` is the older official Homme rendering — include it. |
| **fr** | `Dior Homme` (never “Dior Homme pour homme”) | `General Army Trainer` `basket` `trainer` | Brand stays. |
| **it** | `Dior Homme` | `sneaker` `trainer` `General Army` | Brand stays. |
| **ru** | `Dior Homme` `Диор Омм` `Диор Хом` | `кроссовки` `тренеры` | Latin brand outperforms Cyrillic on RU resale. |

### 4.2 Condition / availability

| Concept | en | ja | ko | zh-Hans | fr | it | ru |
|---|---|---|---|---|---|---|---|
| used | `used` `pre-owned` `secondhand` | **`中古`** `ユーズド` | `중고` `중고품` | `二手` `中古` | `occasion` `seconde main` | `usato` `seconda mano` | `б/у` `секонд-хенд` |
| archive | `archive` `archival` | **`アーカイブ`** | `아카이브` | `档案` `Archive` (Latin wins) | `archive` | `archivio` | `архив` |
| vintage | `vintage` | **`ヴィンテージ`** `ビンテージ` | `빈티지` | `复古` `古着` | `vintage` | `vintage` | `винтаж` |
| thrift / used clothing as a category | `secondhand` | **`古着`** | `구제` `빈티지` | **`古着`** `中古服装` | `friperie` | `vintage` | `секонд` |
| deadstock | `deadstock` `DS` `NWT` `NWOT` | **`デッドストック`** `新品未使用` | `데드스탁` `새제품` | `死库存` `未使用` `全新` | `deadstock` `neuf sans étiquette` | `deadstock` `nuovo` | `дедсток` `новый` |
| unused / new | `new` `BNIB` | `未使用` `新品` `未使用に近い` | `미사용` `새상품` | `全新` `未使用` | `neuf` | `nuovo` | `новое` |
| sold | `sold` `ended` | `売り切れ` `SOLD` `売却済` `落札済` | `판매완료` `판매 완료` | `已售` `卖完` `成交` | `vendu` | `venduto` | `продано` |
| reserved | `pending` | `取引中` `仮押さえ` | `예약` | `待交易` | `réservé` | `riservato` | `забронировано` |
| authentic / authenticated | `authentic` `authenticated` | `正規` `本物` `鑑定済` | `정품` `검수완료` | `正品` `已鉴定` | `authentique` | `autentico` | `оригинал` |
| replica (reject) | `replica` `rep` `1:1` | `レプリカ` `スーパーコピー` | `레플리카` `가품` | `高仿` `复刻` `精仿` | `réplique` | `replica` | `реплика` |

`中古` and `古着` are the two JP tokens that actually retrieve KIND / Komehyo / Mercari / Yahoo clothing. Verified in the shop copy cited above.

### 4.3 Colour / material (seller spelling)

| en | ja | ko | zh-Hans | fr | it | ru |
|---|---|---|---|---|---|---|
| black | `ブラック` `黒` | `블랙` `검정` | `黑` `黑色` | `noir` | `nero` | `чёрный` |
| white | `ホワイト` `白` | `화이트` `흰색` | `白` `白色` | `blanc` | `bianco` | `белый` |
| navy | `ネイビー` | `네이비` | `藏青` `海军蓝` | `marine` | `navy` | `тёмно-синий` |
| grey | `グレー` `グレイ` | `그레이` | `灰` `灰色` | `gris` | `grigio` | `серый` |
| leather | `レザー` `革` `レザーシューズ` | `가죽` | `皮` `皮革` | `cuir` | `pelle` | `кожа` |
| suede | `スエード` `スウェード` | `스웨이드` | `麂皮` `绒面` | `daim` `suède` | `camoscio` | `замша` |
| canvas | `キャンバス` | `캔버스` | `帆布` | `toile` | `tela` | `текстиль` |
| rubber sole | `ラバーソール` | `러버솔` | `橡胶底` | `semelle caoutchouc` | `suola in gomma` | `резина` |

### 4.4 Size conventions

| Market | How sellers write size | Compiler rule |
|---|---|---|
| JP clothing | `サイズS` `2` `44` `46` `48` (EU) plus `日本サイズ` | Emit EU and JP. Slimane-era Homme is often **44/46**. |
| JP shoes | `26cm` `26.5cm` `27cm` + `US 8` | Centimetres dominate Yahoo/Mercari footwear. |
| KR | `250` `260` `270` (mm) + `사이즈` | Millimetres for shoes. |
| CN | `码` `40` `41` `42` `US8` | EU + US mixed. |
| FR/IT | `T.40` `taille 40` `IT 46` `EU 41` | EU apparel / EU shoe. |
| US/UK resale | `US 8` `UK 7` `EU 41` `M` `38` | Always emit US+UK+EU for footwear. |

### 4.5 Query shapes that retrieve (flagship)

Keep the Latin core; add **one** local token per query, do not dump the whole table into one string.

- en: `Dior Homme "General Army Trainer"` / `Dior Homme Army Trainer 07` / `Dior Homme trainer Hedi`
- ja: `ディオールオム トレーナー` / `ディオール オム スニーカー 中古` / `DIOR HOMME アーカイブ 古着` / `ディオールオム デッドストック`
- ko: `디올 옴므 스니커즈 중고` / `Dior Homme 아카이브`
- zh: `Dior Homme 中古` / `迪奥 桀傲 Army Trainer` / `Dior Homme 古着`
- fr: `Dior Homme "Army Trainer" occasion` / `Dior Homme archive basket`
- it: `Dior Homme Army Trainer usato` / `Dior Homme archivio`
- ru: `Dior Homme Army Trainer винтаж`

Yahoo Auctions already indexes the combined form `(ディオールオム diorhomme)` — that is the pattern.

---

## 5. Liveness and sold-state (highest-value sources)

What was **actually observed** vs **unverified**:

| Source | Public sold/removed signal | Confidence |
|---|---|---|
| **eBay API** | `itemEndDate` in the past; `buyingOptions` absent; `getItem` error for ended IDs. This is the intended path. | High (API contract; HTML of `getItem` not fetched this pass). |
| **eBay web `/itm/`** | Common pattern in the wild: 200 + “This listing has ended” or 404. **Not re-fetched** here. Do not use `/sch/`. | Unverified |
| **The RealReal** | robots allow product URLs. Sold PDPs typically 404 or redirect to designer index. **Not re-fetched.** | Unverified |
| **Rebag** | robots allow all. Shopify-class sold-out or 404 expected. Homepage GET redirected to a campaign URL — treat redirects as data. | Unverified |
| **Vinted** | robots allow search/index. Sold listings often remain as 200 with a sold state. **HTML marker unverified.** | Unverified |
| **Mercari JP** | Item URL usually persists; sold shown in-page (`売り切れ`). **HTML marker unverified.** Do not use `/v1/` `/v2/`. | Unverified |
| **Yahoo Auctions** | Live item URL; after close the item page still exists but `/closedsearch` is Disallow. Use the item URL only. | Partial |
| **Buyee** | Proxy of the above; auction-ended copy. | Unverified |
| **Etsy API** | Listing state in the API; web sold shop pages are `Disallow: */shop/*/sold*`. | High for API, n/a for web sold tabs |
| **StockX / GOAT** | Product URL 200 with last-sale; delisted → 404. JS-heavy. | Unverified |
| **SSENSE / Farfetch** | 404 or “sold out” / “this item is no longer available.” | Unverified |
| **KIND / Byronesque / Komehyo** | Shopify/consignment: 404 or “sold out” on PDP. | Unverified |
| **Wikimedia** | 200 vs missing page. Not a listing. | High |
| **Internet Archive** | Always “was live at capture time,” never “is live now.” | High |

**Implementation rule:** a liveness check is a single GET (or official API read) of the **item URL** already in hand. Honor 401/403/429/challenge as **blocked**, not sold. Honor 404/410 as removed. Honor 200 + explicit sold/ended text as sold. Do not hit search URLs that robots Disallow just to see if something is still listed.

---

## 6. Legal and rights posture (launch blocker flags)

### What Searcher may do

| Act | US | EU | UK | Launch flag |
|---|---|---|---|---|
| **Link** to a public listing | Yes. Linking is not copying the work. EU DSM Art. 15 recital: press-publisher rights “should not extend to acts of hyperlinking.” [CELEX 32019L0790](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32019L0790) 2019-04-17, fetched 2026-08-16. | Yes | Yes | Safe core. |
| **Short snippet + title + URL** | Generally OK as a search result (facts + brief quotation). | Art. 15 excludes “individual words or very short extracts” of **press publications**. Product listings are usually not press publications (recital: newspapers/magazines/news sites; scientific journals and non-professional blogs excluded). Fashion editorial *magazines* that Searcher quotes could be Art. 15. | UK did not implement Art. 15. | Snippets of **listings** are lower risk than snippets of *Vogue*/*WWD*. Keep listing snippets short; treat magazine hits as links-only or license. |
| **Thumbnail of a listing photo** | *Kelly v. Arriba Soft* and *Perfect 10 v. Amazon* (9th Cir.): search-engine **thumbnails** can be transformative fair use; in-line **full-size framing** is not. See [en.wikipedia.org/wiki/Perfect_10,_Inc._v._Amazon.com,_Inc.](https://en.wikipedia.org/wiki/Perfect_10,_Inc._v._Amazon.com,_Inc.) and [eff.org/cases/kelly-v-arriba-soft](https://www.eff.org/cases/kelly-v-arriba-soft). 9th Cir. is not the whole US. | No US-style fair use. Depends on quotation exception + (maybe) TDM Art. 4 for the *analysis* copy, not for public display. Public display of a seller’s photo in the EU is the launch risk. | UK fair dealing is narrower than US fair use. Quotation must be fair and attributed. | **Launch flag.** Safest public UI: hotlink or official-API image URL, or a tiny locally cached thumbnail with a rights review. Do not show full-size seller photos from a local mirror. |
| **Cache a copy to compare parts** | Transient technical copies for a search engine are the *Kelly*/*Perfect 10* theory. Not a statute. | Art. 4 TDM: reproductions of **lawfully accessible** works for TDM, retain “as long as is necessary,” **unless reserved by machine-readable means** (Art. 4(3)). Vinted’s robots `Content-Signal: ai-train=no` / `ai-input=yes` / `search=yes` is exactly such a reservation for training, and an allowance for search. eBay’s preamble forbids robots except search engines / official API. | UK TDM exception is research-oriented and was not expanded to commercial TDM the EU way. **Unverified** against current UK IPO text this pass. | Internal feature-comparison cache: restrict to sources that have not reserved TDM; keep transient; do not publish the cache. |
| **Mirror a listing page** | No. That is not a search engine. | No. | No. | Never. |
| **Brave / Marginalia / Etsy / eBay API results** | Contract, not copyright, is the constraint. Brave ToS 11 Feb 2026 §3.2(i): no result database except transient. Etsy: 6-hour listing freshness. Marginalia default CC-BY-NC-SA — a commercial public launch needs the commercial key. | Same contracts apply. | Same. | **Launch flag:** Brave storage-rights plan or transient-only; Marginalia commercial key before a paid/public product; Etsy cache clock. |

### Other launch blockers

- **eBay/Etsy web scraping** — primary terms/robots forbid it. A public launch that scrapes them is a contract and CFAA/risk story. Use the APIs or omit the source.
- **SerpAPI/Serper** — they scrape Google. Admitting them is a policy choice that sits next to Searcher’s own “no bypass” rule.
- **Common Crawl AI indemnity** — ToU §9 expressly indemnifies CC against claims from using Crawled Content in AI systems. Searcher’s part-level model that trains or embeds CC HTML needs counsel.
- **Replica lane in a public UI** — even if listings are rejected from Real/Possibly Real, a public product that *indexes* self-declared fakes will attract brand-enforcement mail. Keep that lane internal.
- **Vinted Content-Signal** — search=yes, ai-train=no. A later model-training pass on Vinted bodies is reserved under Art. 4(3).
- **EU database sui generis** — repeatedly extracting a “substantial part” of a marketplace’s listing database can be a separate right from copyright. Volume + regularity is the fact pattern. Sitemap-scale mirroring of RealReal/SSENSE is how you walk into it.

---

## A–G answers (compressed, cited)

### A. General web / image discovery

| Candidate | robots / access | Official API | Credential | Free tier (2026-08-16) | Automated querying / storage | Zero-cred? |
|---|---|---|---|---|---|---|
| **SearxNG self-hosted** | n/a (you run it) | Yes, `/search` JSON/CSV/RSS [docs 2026.8.14](https://docs.searxng.org/dev/search_api.html) | no | unlimited locally | Your instance, your logs. Upstream engines have their own robots/ToS. | **Yes** |
| **SearxNG public instances** | instance-specific | same API, often JSON **disabled** | no | n/a | Docs warn of logging risk and upstream bans. | Technically yes, **do not use** as production |
| **Brave Search API** | n/a (API) | Yes, web/images/news/videos/LLM | **yes** + card | $5 credit / mo ≈ 1,000 Search req | ToS 11 Feb 2026: no result DB except transient; no train; no resell. Storage-rights plan extra. | No |
| **Serper** | n/a | Yes (`google.serper.dev`) | **yes** | 2,500 trial credits, no card ([serper.dev](https://serper.dev/)) | ToS 29 May 2024: scraped public pages; no Google affiliation; no as-is mirroring. | No |
| **SerpAPI** | n/a | Yes | **yes** | 250/mo on free (third-party 2026 writeups; confirm on dashboard) | ToS 8 Apr 2026; “Legal Shield” on paid plans. | No |
| **Google CSE JSON** | n/a | Closed to new customers; dies 1 Jan 2027 | n/a | n/a | n/a | No |
| **Bing Web Search v7** | n/a | Retired 11 Aug 2025 | n/a | n/a | Grounding-with-Bing is not a drop-in | No |
| **Marginalia** | their crawl honors robots | `api2.marginalia-search.com` | `public` or emailed key | `public` key, shared 503s | CC-BY-NC-SA 4.0 default | **Yes** (`public`) |
| **Common Crawl** | CCBot honors robots | CDX/S3, not live search | no | dataset free | ToU 7 Mar 2024: respect third-party rights; AI indemnity | **Yes** (offline) |
| **Openverse** | n/a | `api.openverse.org/v1` | optional OAuth | anonymous throttle | CC-licensed works | **Yes** (throttled) |
| **TinEye** | n/a | commercial API | **yes** | none commercial | Legal: free = non-commercial only | No |
| **Wikimedia** | article pages allowed | Action API | no | n/a | Follow UA + license on reuse | **Yes** |
| **DuckDuckGo HTML** | `Allow: /` | no official JSON | no | n/a | ToS for bots **unverified** | Practically yes, legally `review_required` |
| **Google Lens / Bing Visual** | n/a | no public general API in 2026 | — | — | — | No |

**Zero-credential:** SearxNG (self-hosted), Marginalia `public`, Wikimedia, Common Crawl, Openverse (low tier), Internet Archive, DuckDuckGo HTML (review).  
**Need a key:** Brave, eBay, Etsy, TinEye, Serper, SerpAPI, Openverse standard, Marginalia private.  
**Sanest default:** self-hosted SearxNG + Marginalia `public` + Wikimedia. First key = Brave.

### B. Western marketplaces

Covered in the launch table. Extra notes:

- **eBay web** is not a crawl target. robots.txt July 2026 says so in the file header and Disallows `/sch/`.
- **Etsy web search** Disallow `/search?*q=`; official API is the path; screen-scraping forbidden.
- **Grailed, Vestiaire, Depop** could not even serve robots.txt to this host — `blocked`.
- **JSON-LD / no-JS / sold-in-HTML:** **unverified** on live PDPs this pass (Rebag redirected; luxury sites JS-heavy; eBay developer HTML errored). Shopify-class stores (KIND, many consignment) typically emit `Product` JSON-LD — treat as a hypothesis to confirm on first admitted GET, not as a fact.
- **Farfetch, SSENSE, StockX, GOAT, Poshmark:** product pages not disallowed; **search URLs are**. Use web/API discovery, then GET the product URL.
- **The RealReal:** sitemap-first. No public API found.

### C. JP / KR / CN and agents

Covered in the launch table. Short classification:

| Source | Public fetch | Account | App | Closed |
|---|---|---|---|---|
| Yahoo Auctions item HTML | likely | to bid | no | official API **gone** (404) |
| Mercari JP item HTML | likely | to buy/chat | app exists | `/v1` `/v2` disallowed |
| Rakuten | partial | — | — | `/shops/` disallowed |
| ZOZO | — | — | — | robots fetch **failed** |
| Rakuma item | likely | — | — | `/search/` disallowed |
| 2nd Street | — | — | — | Akamai **denied** |
| Komehyo | yes | — | — | open robots |
| RAGTAG | SERP exists | — | — | robots fetch **failed** |
| KIND | product yes | — | — | `/search` disallowed |
| Taobao | `/list` only | item pages often yes | often | `/*?*` disallowed |
| Xianyu/Goofish | robots open | often | often | unverified |
| Weidian | — | typically | typically | robots **404** |
| 1688 | no (Googlebot `/`) | — | — | **blocked** |
| Poizon web | product maybe | — | **yes** | `/search` disallowed |
| Bunjang | robots open | — | strong app | unverified JS |
| KREAM | — | — | **yes** | robots empty |
| Buyee public | yes | to buy | no | link only |

### D. Replica

See §3. Legitimate path = admitted search APIs + public URLs. No detection-evasion. Self-declared replica → internal reject.

### E. Multilingual

See §4. Exact tokens, not descriptions.

### F. Liveness

See §5. Highest-confidence sold-state today is **eBay Browse `getItem` / `itemEndDate`**. Everything else is a single item-URL GET with honest blocked/sold/live labels.

### G. Rights

See §6. Public launch can **link**. Thumbnails and caches are the counsel items. Brave/Etsy/Marginalia contracts constrain storage even when copyright would not.

---

## 5. What is NOT admissible and why

| Target | Why |
|---|---|
| eBay `/sch/` and any eBay HTML crawl used as a search engine | robots.txt v29_COM_July_2026 header + `Disallow: /sch/` |
| Etsy HTML search / scraping | robots `Disallow: /search?*q=`; API docs: “Screen-scraping is not allowed.” |
| Grailed, Vestiaire, Depop (this host, this date) | Cloudflare/bot interstitial on robots and terms |
| ZOZO, 2nd Street, RAGTAG robots, Weidian robots, KREAM robots | Fetch failed or empty — treat as blocked until a clean robots.txt is read |
| 1688 as a Googlebot-class client | `User-agent: Googlebot` `Disallow: /` |
| Taobao item URLs with `?` | `Disallow: /*?*` |
| StockX/GOAT/Farfetch/SSENSE/Poshmark/KIND **search URLs** | explicit `Disallow: /search` (or equivalent) |
| Mercari `/v1/` `/v2/`, Buyee `/api/v1/` `/internalapi/` | robots Disallow (private/app APIs) |
| Yahoo `/closedsearch`, member/watchlist/sell | robots Disallow |
| Google CSE (new), Bing v7 | closed / retired |
| Direct Google or Bing HTML scraping | no license; CAPTCHA is an access control |
| Public SearxNG instances as the production backend | official docs: untrusted operators + upstream bans |
| Any source that answers with CAPTCHA, login, app-only empty shell, or 403 | `blocked`, never “0 results” |
| Identity rotation, proxy pools, browser-profile theft | forbidden by the product constraint (and by Brave ToS §3.2(v), Wikimedia API policy, CC FAQ “don't use proxy networks”) |
| Buying, bidding, or agent checkout | out of scope; Buyee/eBay/Vinted all forbid automated checkout |
| Publishing self-declared replicas on Real / Possibly Real | product requirement |
| Mirroring listing pages or building a durable Brave-result database without a storage plan | Brave ToS; copyright |

---

## 6. Open questions a human must decide

1. **Thumbnails in the public UI.** US case law is friendly; EU public display of seller photos is not settled by *Kelly*. Ship links-only in the EU/UK, or get counsel.
2. **Brave storage-rights plan vs transient cache.** Required if Searcher persists snippets beyond a request.
3. **Marginalia CC-BY-NC-SA.** A commercial public Searcher needs their commercial key.
4. **Serper / SerpAPI.** Admitting a Google-scrape vendor is in tension with “no bypass.” Default: no.
5. **Etsy/eBay developer agreements** — full license text for eBay did not render (ebay.com error pages). A human should accept those agreements and paste the storage/display clauses into `SOURCE_POLICY.md`.
6. **Vinted `ai-input=yes` + `search=yes`.** Does part-level comparison count as search or as AI-input? Their definition: search = “hyperlinks and short excerpts”; ai-input = RAG/grounding. Searcher’s comparator is closer to ai-input, which they allow — but confirm.
7. **Is `shopheroine.com` the Heroine you mean?** robots are open; identity of the storefront was not otherwise verified.
8. **JP sources whose robots.txt could not be read** (ZOZO, 2nd Street, RAGTAG). Worth a second fetch from a non-blocked network; until then they stay `blocked`.
9. **UK TDM / quotation** — current IPO text not fetched. Do not assume EU Art. 4 exists in the UK.
10. **Common Crawl inside a commercial ranking model** — ToU AI indemnity + third-party copyright. Counsel.
11. **Replica internal lane** vs brand-enforcement risk even if hidden from public tabs.
12. **JSON-LD / no-JS / sold markers** on RealReal, Rebag, Mercari, Vinted, Yahoo, StockX — labelled unverified. First implementation task is one admitted GET per source and a one-line update to this table.

---

## SUMMARY

Public, legitimate search for rare clothing on day one is: **self-hosted SearxNG + Wikimedia + Marginalia `public` + Internet Archive + Common Crawl (offline) + robots-allowed product URLs** (RealReal, Rebag, Komehyo, KIND products, Byronesque, Vinted items, Mercari/Yahoo items, Buyee public pages). The first key to add is **Brave** (web+image). The first marketplace keys are **eBay Browse** and **Etsy Open API**. Grailed, Vestiaire, Depop, ZOZO, Weidian, and 1688 are **not admitted** on this evidence. Google CSE is closed to new customers; Bing Search API is retired. Replica sources are for alias/hard-negative use via public search only; self-declared fakes never appear on Real / Possibly Real.

## FILES CHANGED
none

## DECISIONS MADE
- Classified sources as `admitted` / `blocked` / `review_required` solely from primary robots.txt, official API docs, and terms fetched 2026-08-16.
- Treated Cloudflare/Akamai/empty-robots failures as `blocked`, not as “try harder.”
- Recommended self-hosted SearxNG + Marginalia `public` + Wikimedia as the zero-credential default; Brave as the first paid key.
- Refused Serper/SerpAPI as a default because they scrape Google.
- Restricted replica material to internal reject / alias evidence.

## ASSUMPTIONS
- “Heroine” maps to `shopheroine.com` (robots open; storefront identity not independently confirmed).
- Shopify-class PDPs will expose usable HTML/JSON-LD; not confirmed on a live KIND/Rebag item.
- Yahoo Auctions item pages remain HTML-fetchable without login; only the official API 404 was confirmed.
- Vinted Content-Signal `search=yes` covers Searcher’s public result cards.

## DEVIATIONS FROM CONTRACT
- Did not successfully fetch live listing HTML to confirm JSON-LD / no-JS / sold DOM markers for most marketplaces (Rebag redirected; Grailed/Vestiaire/Depop blocked; eBay developer HTML errored). Those cells are labelled unverified instead of guessed.
- Did not fetch FromJapan, ZenMarket, Superbuy, Pandabuy, CSSBuy, or CNFans terms.
- Did not fetch the full eBay API License Agreement body (host returned an eBay error page).
- Etsy `/legal/api` required JS; caching/scraping quotes come from the developer docs page plus a search excerpt of the legal page.

## TESTS RUN
- HTTP GET of robots.txt / official docs / terms for the sources listed (2026-08-16). Decisive lines quoted above with URLs.

## TESTS OMITTED
- Browser rendering of JS listing pages.
- Actual API calls (would require keys / sign-up).
- Counsel review of thumbnail/TDM questions.

## KNOWN LIMITATIONS
- One vantage point (this host). Region gates may differ.
- robots.txt can change without notice (eBay file is versioned `v29_COM_July_2026`).
- Structured-data and sold-state columns need a single admitted GET per source before adapter work.

## POSSIBLE REGRESSIONS
none (read-only; no repo changes)

## REMAINING WORK
- One admitted GET per `review_required` source to fill JSON-LD / sold-marker cells.
- Human decisions in §6.
- Re-fetch ZOZO / RAGTAG / 2nd Street / Weidian robots from a clean path.
- Counsel on thumbnails, Brave storage, Marginalia NC-SA, CC-in-model.

## CONFIDENCE
medium

Would go to **high** after: (1) one successful product-page GET each for RealReal, Mercari, Yahoo Auctions, Vinted, KIND; (2) readable eBay API License + Etsy API Terms HTML; (3) counsel note on EU thumbnails and SerpAPI. Admissibility calls that rest on robots.txt and official “API closed/retired/use the API” sentences are already high-confidence.
