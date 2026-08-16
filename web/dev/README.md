# Development stub

Not part of the product. Not published to GitHub Pages.

`stub_api.py` is superseded for local end-to-end use by the real API:

```text
scripts/run_api.sh
```

That binds `127.0.0.1:8765` and serves `web/` so `config.js` needs no edit.

The stub remains as a fixture-driven UI harness (scripted scenarios, no
engine). Prefer the real API when checking campaign honesty.
