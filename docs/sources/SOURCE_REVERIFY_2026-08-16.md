# Pending-source re-verify (2026-08-16)

Browser-rendered fetch of robots.txt and a typical product URL for each
pending marketplace. Honest User-Agent. No challenge solving.

Admission status is unchanged: every source below stays `review_required`
and disabled. The existing unit lock
`test_pending_scope_adapters_are_disabled_review_required` requires that.
Recorded notes now match what was observed.

Raw captures: `artifacts/deepverify/source-reverify.json`.

| Source | Product-URL robots rule | Challenge | Admission |
|---|---|---|---|
| depop | Browser robots.txt is real. `Disallow: /search/*`, magic-link, selling/sold/likes, filter queries. `/products/` is allowed. | No. Plain HTTP robots and item URLs are 403 Forbidden HTML, not a Cloudflare interstitial. Browser placeholder item was 404. | `review_required` (disabled). Not enabled: honest HTTP is 403. |
| grailed | robots.txt fetchable over HTTP and browser. `Disallow: /search`, `/listings/*/edit`, account/checkout. `/listings/<id>` allowed. | Yes. Listing page is Cloudflare "Just a moment" over HTTP and browser. Recorded `BLOCKED_BY_CHALLENGE`. | `review_required` (disabled). |
| vestiaire | HTTP robots.txt is a Cloudflare interstitial. Browser robots.txt is real: `Disallow: /admin/ /api/ /members/` checkout. | Yes on HTTP robots and HTTP listing. Browser `/women/` returned 200 without a challenge. | `review_required` (disabled). |
| taobao | `Allow: /$` `/list/*` `/list/*?*`. `Disallow: /*?*`. Typical item URLs are query-string `item.htm` and fall under that Disallow. | Browser follow of an item URL reached a login/captcha page. Should not be fetched: the written rule disallows it. | `review_required` (disabled). `page_fetch=false`. |
| weidian | `robots.txt` still redirects to `h5.weidian.com/m/abnormal/404.html` (200 HTML, not a robots file) over HTTP and browser. | No. | `review_required` (disabled). `page_fetch=false`. Fail-closed until a real robots.txt exists. |
| yupoo | `www.yupoo.com/robots.txt` and `/albums/` redirect to `x.yupoo.com/404`. No robots file. | No. | `review_required` (disabled). `page_fetch=false`. |

None of these six are now permitted for live fetch. Enabling a source that
turns out to be robots-allowed still requires lifting the existing test lock
and a terms review; that is outside this lane.
