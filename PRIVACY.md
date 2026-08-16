# Privacy

Bible §29.6. This document describes the local engine this repository
ships. There is no hosted Searcher service.

## Uploads are private and local by default

Images, text, and tags stay on the machine that runs the API. The
default data root is `data/` under the repository (override with
`SEARCHER_DATA_ROOT`). `PrivacySettings.retention` defaults to
`session`. `training_opt_in` is refused by the schema: constructing
it as `true` raises.

The static UI (`web/`) stores only local drafts, display preferences,
and recent search identifiers in the browser. It has no accounts and
no third-party scripts.

## No training use

Nothing in this tree trains a model on user uploads. Feedback
(`POST /v1/results/{id}/feedback`) is stored as a signed local
evidence record plus a `FeedbackReceipt`. It does not promote, demote,
or train anything (`applied: false`).

## No telemetry

There is no analytics product, no crash reporter, and no outbound
phone-home.

API request logs are structured JSON on stderr: request id, method, a
sanitized path, status, and duration. They do not carry upload bytes,
filenames, private paths, secrets, or listing bodies. See
`src/searcher/api/logging.py`.

## No third-party model upload

There is no configured mode that uploads user images or listing pixels
to a third-party model host. Learned embeddings, if they ever run,
activate only when weights already exist locally; nothing is
downloaded (`docs/architecture/MATCHING_AND_AUTHENTICITY.md`). A
future explicit mode would have to be added in code and documented
here before it existed.

VisionMCP is an in-process library import of a locally installed pin,
not a cloud call.

## Deletion

`DELETE /v1/searches/{search_id}` returns `204`. Subsequent reads of
that search or its results are `404`.

**Removed**

- campaign-private object-store artifacts
- user reference uploads
- campaign events
- candidates and results
- user text and tags
- the corresponding private SQLite rows

**Retained**

- receipts, including the `DeletionReceipt` itself
- shared content-addressed objects that another campaign still owns

The receipt states both lists. Evidence:
`CampaignController.delete` and
`tests/integration/test_api.py::test_refresh_feedback_delete`.

Deleting one campaign cannot raise another campaign's score
(`tests/property/test_p03_delete_evidence.py` on the interval
primitive; `tests/property/test_p07_campaign_isolation.py` on the
store).

## What the static page retains

After a delete, the engine is gone. The browser may still hold a
draft or a recent-search id until the user clears site data. That is
browser storage, not the API.

## Diagnostics

Receipts and capability probes are inspectable locally. Export is an
operator action. The UI never embeds a secret, token, or credential.
The API address is deployment configuration (`?api=` on the page, or
`web/config.js`).
