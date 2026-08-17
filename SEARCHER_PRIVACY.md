# Searcher privacy

Bible §39 name. Draws from `PRIVACY.md` (Bible §29.6). This file is
the §39 binding.

There is no hosted Searcher service. This document describes the
local engine.

## Uploads stay on the machine that runs the API

Default data root is `data/` under the repository
(`SEARCHER_DATA_ROOT`). `PrivacySettings.retention` defaults to
`session`. `training_opt_in` cannot be constructed as `true`.

The static UI stores only local drafts, display preferences, and
recent search identifiers. It has no accounts and no third-party
scripts.

## No training, no telemetry, no third-party model upload

Feedback (`POST /v1/results/{id}/feedback`) is a signed local
evidence record. It does not promote, demote, or train
(`applied: false`).

API request logs are structured JSON on stderr: request id, method,
sanitized path, status, duration. They do not carry upload bytes,
filenames, private paths, secrets, or listing bodies
(`src/searcher/api/logging.py`).

Learned embeddings activate only from a local weights file. A search
never downloads weights. VisionMCP is an in-process import of a
locally installed pin, not a cloud call.

## Deletion

`DELETE /v1/searches/{search_id}` returns `204`. Subsequent reads
are `404`.

Removed: campaign-private object-store artifacts, user reference
uploads, events, candidates, results, user text and tags, the
corresponding private SQLite rows.

Retained: receipts, including the `DeletionReceipt`; shared
content-addressed objects that another campaign still owns.

Evidence: `CampaignController.delete` and
`tests/integration/test_api.py::test_refresh_feedback_delete`.

Deleting one campaign cannot raise another campaign's score
(`tests/property/test_p03_delete_evidence.py`,
`tests/property/test_p07_campaign_isolation.py`).

## What the static page retains

After a delete, the browser may still hold a draft or a recent-
search id until the user clears site data.

## What is not established

- A formal privacy-impact assessment.
- That every log line on a live operator host has been sampled
  and found free of user image bytes. The code path omits them;
  a production log dump at this SHA is not in the tree.
