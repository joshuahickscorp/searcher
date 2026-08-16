# Before — listing index stored as a product

Measured on this host, 2026-08-16, through the real API: a live campaign
fetched 11 pages, normalized exactly **1** candidate, and that candidate's
canonical URL was:

    https://shop.kind.co.jp/collections/name-willy/products.json?limit=250

That URL is a Shopify collection feed. It was stored as a single candidate
with **zero** images, then hidden for having no evidence.

Related:

- `artifacts/searcher-adversarial-recall.receipt.json` — 21 live searches, 0 found
- `artifacts/realmatch/known_item_summary.json` — a later run that did attach
  KIND product images and ranked the known listing first (item match 0.569)

The classifier treated `/collections/.../products.json` as a product because
the path contains `/products/`. When the Shopify JSON parse returned nothing
(or was skipped), generic HTML extract produced one imageless listing at the
feed URL.
