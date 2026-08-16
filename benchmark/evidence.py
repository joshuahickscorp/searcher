"""Self-contained evidence board. No external requests."""

from __future__ import annotations

import base64
import html
import io
from typing import Any

from PIL import Image

from . import SHIPPED_THRESHOLD
from .buckets import BucketReport
from .degradations import DEGRADATION_NAMES
from .retrieval import QueryResult, RetrievalReport
from .splits import SplitSet


def _data_uri(data: bytes, *, max_edge: int = 168) -> str:
    image = Image.open(io.BytesIO(data)).convert("RGB")
    image.thumbnail((max_edge, max_edge))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=68, optimize=True)
    payload = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}"


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _pct(value: float | None) -> str:
    if value is None:
        return "not computed"
    return f"{value * 100:.1f}%"


def _curve_svg(curve: dict[str, Any]) -> str:
    bins = list(curve.get("bins") or [])
    if not bins:
        return "<p>No calibration bins.</p>"
    width = 640
    height = 220
    left, right, top, bottom = 44, 16, 16, 36
    plot_w = width - left - right
    plot_h = height - top - bottom
    bars: list[str] = []
    n = len(bins)
    bar_w = plot_w / max(1, n)
    max_count = max((int(row["n"]) for row in bins), default=1) or 1
    for index, row in enumerate(bins):
        count = int(row["n"])
        bh = 0 if max_count == 0 else (count / max_count) * (plot_h - 8)
        x = left + index * bar_w + 2
        y = top + (plot_h - bh)
        pos = int(row["n_positive"])
        pos_h = 0 if count == 0 else (pos / max_count) * (plot_h - 8)
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 4:.1f}" '
            f'height="{bh:.1f}" fill="#c5cdd6"/>'
        )
        bars.append(
            f'<rect x="{x:.1f}" y="{top + plot_h - pos_h:.1f}" width="{bar_w - 4:.1f}" '
            f'height="{pos_h:.1f}" fill="#2f6fed"/>'
        )
        if count:
            bars.append(
                f'<text x="{x + (bar_w - 4) / 2:.1f}" y="{y - 3:.1f}" '
                f'text-anchor="middle" class="svg-n">{count}</text>'
            )
    threshold = float(curve.get("shipped_threshold") or SHIPPED_THRESHOLD)
    tx = left + threshold * plot_w
    line = (
        f'<line x1="{tx:.1f}" y1="{top}" x2="{tx:.1f}" y2="{top + plot_h}" '
        f'stroke="#b42318" stroke-width="2" stroke-dasharray="4 3"/>'
        f'<text x="{tx + 4:.1f}" y="{top + 12}" class="svg-t">threshold {threshold}</text>'
    )
    axis = (
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" '
        f'y2="{top + plot_h}" stroke="#222"/>'
        f'<text x="{left}" y="{height - 8}" class="svg-n">0</text>'
        f'<text x="{left + plot_w}" y="{height - 8}" text-anchor="end" class="svg-n">1</text>'
        f'<text x="{left + plot_w / 2}" y="{height - 8}" text-anchor="middle" '
        f'class="svg-n">score</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Calibration histogram">'
        f"<style>.svg-n{{font:11px ui-sans-serif,system-ui,sans-serif;fill:#222}}"
        f".svg-t{{font:11px ui-sans-serif,system-ui,sans-serif;fill:#b42318}}</style>"
        f"{''.join(bars)}{line}{axis}</svg>"
    )


def _retrieval_row(query: QueryResult) -> str:
    top = query.ranking[:5]
    cards = []
    gallery = query.gallery_bytes
    ref_blob = gallery.get(query.target_id)
    if ref_blob is not None:
        cards.append(
            "<figure class='card ref'>"
            f"<img src='{_data_uri(ref_blob)}' alt='reference listing'/>"
            f"<figcaption>Reference · {_esc(query.reference_image)}</figcaption>"
            "</figure>"
        )
    cards.append(
        "<figure class='card query'>"
        f"<img src='{_data_uri(query.query_bytes)}' alt='query {_esc(query.degradation)}'/>"
        f"<figcaption>Query · {_esc(query.degradation)} · {_esc(query.query_image)}</figcaption>"
        "</figure>"
    )
    for index, row in enumerate(top, start=1):
        blob = gallery.get(row.item_id)
        img = "" if blob is None else f"<img src='{_data_uri(blob)}' alt='candidate {index}'/>"
        mark = "correct" if row.correct else "wrong"
        cards.append(
            f"<figure class='card {mark}'>"
            f"{img}"
            f"<figcaption>#{index} · score {row.score:.3f} · {_esc(row.item_id)}"
            f"<br/>{'correct listing' if row.correct else 'not the listing'}"
            f"</figcaption></figure>"
        )
    rank_txt = "not retrieved" if query.rank is None else f"rank {query.rank}"
    return (
        f"<article class='query-row'>"
        f"<header><strong>{_esc(query.target_id)}</strong> · {_esc(query.degradation)}"
        f" · {rank_txt}</header>"
        f"<div class='strip'>{''.join(cards)}</div></article>"
    )


def _bucket_row(row: Any) -> str:
    ref = "" if row.reference_preview is None else _data_uri(row.reference_preview)
    cand = "" if row.preview is None else _data_uri(row.preview)
    verdict = "correct" if row.correct else "wrong"
    expensive = row.predicted == "real" and row.truth != "real"
    flag = " <span class='expensive'>FALSE REAL</span>" if expensive else ""
    case_cap = f"<figcaption>{_esc(row.case_id)}</figcaption>"
    scores = (
        f"item-match ≥ {row.item_match_lower:.2f} · "
        f"authenticity ≥ {row.authenticity_lower:.2f} · "
        f"completeness {row.completeness:.2f}"
    )
    return (
        f"<article class='bucket-row {verdict}'>"
        f"<figure><img src='{ref}' alt='reference'/>"
        f"<figcaption>Reference</figcaption></figure>"
        f"<figure><img src='{cand}' alt='candidate'/>{case_cap}</figure>"
        f"<div class='bucket-meta'>"
        f"<p><strong>{_esc(row.item_id)}</strong>{flag}</p>"
        f"<p>Truth: <span class='pill {_esc(row.truth)}'>{_esc(row.truth)}</span> · "
        f"Predicted: <span class='pill {_esc(row.predicted)}'>{_esc(row.predicted)}</span></p>"
        f"<p>{_esc(scores)}</p>"
        f"<p class='reasons'>{_esc(', '.join(row.reasons) or 'no reason codes')}</p>"
        f"</div></article>"
    )


def render_board(
    *,
    splits: SplitSet,
    retrieval: RetrievalReport,
    buckets: BucketReport,
    calibration: dict[str, Any],
    operational: dict[str, Any],
    identity: dict[str, Any],
    not_computed: list[dict[str, str]],
    does_not_cover: list[str],
    adversarial: dict[str, Any] | None,
) -> str:
    overall = retrieval.as_payload()["overall"]
    bucket_payload = buckets.as_payload()
    false_real = bucket_payload["false_real"]
    deg_rows = []
    by_deg = retrieval.as_payload()["by_degradation"]
    for name in DEGRADATION_NAMES:
        block = by_deg[name]
        deg_rows.append(
            "<tr>"
            f"<td>{_esc(name)}</td>"
            f"<td>{block['n']}</td>"
            f"<td>{_pct(block['recall_at_1'])}</td>"
            f"<td>{_pct(block['recall_at_5'])}</td>"
            f"<td>{_pct(block['recall_at_10'])}</td>"
            f"<td>{block['mrr']:.3f}</td>"
            "</tr>"
        )
    query_html = [_retrieval_row(query) for query in retrieval.queries]

    conf_rows = []
    matrix = bucket_payload["confusion"]
    labels = bucket_payload["labels"]
    head = "".join(f"<th>pred {_esc(label)}</th>" for label in labels)
    for truth in labels:
        cells = "".join(f"<td>{matrix.get(truth, {}).get(pred, 0)}</td>" for pred in labels)
        conf_rows.append(f"<tr><th>truth {_esc(truth)}</th>{cells}</tr>")

    pr_rows = []
    for label in labels:
        pr_rows.append(
            "<tr>"
            f"<td>{_esc(label)}</td>"
            f"<td>{_pct(bucket_payload['precision'].get(label))}</td>"
            f"<td>{_pct(bucket_payload['recall'].get(label))}</td>"
            "</tr>"
        )

    missing = (
        "".join(
            f"<li><code>{_esc(row.get('id'))}</code> — {_esc(row.get('reason'))}</li>"
            for row in not_computed
        )
        or "<li>None.</li>"
    )
    limits = "".join(f"<li>{_esc(line)}</li>" for line in does_not_cover)
    adv = ""
    if adversarial:
        adv = (
            "<section><h2>Live end-to-end recall (prior finding)</h2>"
            "<p>The earlier live campaign on three KIND product URLs finished "
            "in about two seconds with <em>coverage exhausted</em> and zero "
            "published results. That is a discovery-coverage finding, not a "
            "ranking score to beat. Those three listings are not in the cached "
            "fixture pack this benchmark is authorized to use.</p>"
            f"<pre>{_esc(adversarial.get('summary'))}</pre></section>"
        )

    false_box = (
        f"<aside class='callout'>"
        f"<h2>False Real</h2>"
        f"<p class='big'>{false_real['count']}</p>"
        f"<p>of {false_real['n']} held-out cases "
        f"({_pct(false_real['rate_among_all'])} of all; "
        f"{_pct(false_real['rate_among_not_real'])} of labelled-not-Real).</p>"
        f"<p>{_esc(false_real['note'])}</p>"
        f"<p>ids: {_esc(', '.join(false_real['ids']) or 'none')}</p>"
        f"</aside>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Searcher public benchmark — evidence board</title>
<style>
:root {{ color-scheme: light; }}
body {{ margin: 0; font: 16px/1.45 ui-sans-serif, system-ui, -apple-system, sans-serif;
  color: #1b1f24; background: #f4f1ea; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 28px 20px 80px; }}
h1, h2, h3 {{ font-weight: 650; letter-spacing: -0.02em; }}
h1 {{ font-size: 1.8rem; margin-bottom: 0.2rem; }}
.lede {{ font-size: 1.05rem; max-width: 70ch; }}
section {{ background: #fff; border: 1px solid #d7d2c8; border-radius: 12px;
  padding: 18px 18px 8px; margin: 18px 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0 18px; }}
th, td {{ border: 1px solid #d7d2c8; padding: 6px 8px; text-align: left; font-size: 0.92rem; }}
th {{ background: #eef2f6; }}
.strip {{ display: flex; gap: 10px; overflow-x: auto; padding-bottom: 8px; }}
.card, .bucket-row figure {{ margin: 0; width: 168px; flex: 0 0 auto; }}
.card img, .bucket-row img {{ width: 168px; height: 168px; object-fit: contain;
  background: #eceae4; border: 1px solid #ccc; display: block; }}
.card figcaption, .bucket-row figcaption {{ font-size: 0.78rem; padding-top: 4px; }}
.card.correct {{ outline: 3px solid #1b7f3a; }}
.card.wrong {{ outline: 1px solid #bbb; }}
.card.query {{ outline: 3px solid #2f6fed; }}
.card.ref {{ outline: 3px solid #6b5b3a; }}
.query-row, .bucket-row {{ margin: 14px 0 22px; }}
.bucket-row {{ display: flex; gap: 14px; align-items: flex-start; flex-wrap: wrap; }}
.bucket-row.wrong {{ background: #fff4f2; padding: 10px; border-radius: 8px; }}
.pill {{ display: inline-block; padding: 1px 8px; border-radius: 999px;
  background: #e8edf3; font-size: 0.85rem; }}
.pill.real {{ background: #d8f3df; }}
.pill.possibly_real {{ background: #fff3c4; }}
.pill.replica {{ background: #f3d8ee; }}
.pill.hidden {{ background: #e4e4e4; }}
.callout {{ background: #fff4f2; border: 2px solid #b42318; border-radius: 12px;
  padding: 12px 16px; margin: 18px 0; }}
.callout .big {{ font-size: 3rem; margin: 0; line-height: 1; }}
.expensive {{ color: #b42318; font-weight: 700; }}
.meta {{ color: #444; font-size: 0.9rem; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.88em; }}
.reasons {{ color: #444; font-size: 0.85rem; }}
svg {{ width: 100%; height: auto; background: #fff; }}
.legend span {{ display: inline-block; width: 12px; height: 12px; margin-right: 4px; }}
</style>
</head>
<body>
<main>
<h1>Searcher evidence board</h1>
<p class="lede">A held-out evaluation of retrieval and bucket decisions on
data this project is already permitted to hold. Numbers are measurements,
not claims of authenticity and not a comparison with conventional image
search. Anyone can regenerate this page with
<code>uv run python -m benchmark.run --all</code>.</p>
<p class="meta">host {_esc(identity.get("host"))} · git {_esc(identity.get("git_sha"))}
 · code {_esc(identity.get("code_version"))} · measured {_esc(identity.get("measured_at"))}
 · scorer {_esc(retrieval.scorer.identity)}</p>

<section>
<h2>What you are looking at</h2>
<p>Each retrieval row is one query photograph (blue outline) beside the top
five gallery listings. Green outline means that candidate is the same listing
as the query. Each bucket row is a constructed case: the reference shoe on
the left, the candidate on the right, and the engine's public bucket versus
the constructed label.</p>
<p>Calibration split hash <code>{_esc(splits.hash_for("calibration"))}</code>.
Held-out split hash <code>{_esc(splits.hash_for("held_out"))}</code>.
An identifier appears in exactly one split.</p>
</section>

{false_box}

<section>
<h2>Retrieval (held-out)</h2>
<p>{_esc(retrieval.protocol)}</p>
<table>
<thead><tr><th>set</th><th>n</th><th>recall@1</th><th>recall@5</th><th>recall@10</th><th>MRR</th></tr></thead>
<tbody>
<tr><td>overall</td><td>{overall["n"]}</td><td>{_pct(overall["recall_at_1"])}</td>
<td>{_pct(overall["recall_at_5"])}</td><td>{_pct(overall["recall_at_10"])}</td>
<td>{overall["mrr"]:.3f}</td></tr>
{"".join(deg_rows)}
</tbody></table>
{"".join(query_html)}
</section>

<section>
<h2>Bucket decisions (held-out)</h2>
<p>{_esc(buckets.protocol)}</p>
<table>
<thead><tr><th>label</th><th>precision</th><th>recall</th></tr></thead>
<tbody>{"".join(pr_rows)}</tbody>
</table>
<table>
<thead><tr><th></th>{head}</tr></thead>
<tbody>{"".join(conf_rows)}</tbody>
</table>
{"".join(_bucket_row(row) for row in buckets.rows)}
</section>

<section>
<h2>Calibration curve (calibration split only)</h2>
<p>{_esc(calibration.get("protocol"))}</p>
<p>{_esc(calibration.get("threshold_bin_note"))}</p>
<p class="legend"><span style="background:#2f6fed"></span> same-listing pairs
<span style="background:#c5cdd6;margin-left:12px"></span> all pairs
<span style="background:#b42318;margin-left:12px"></span> shipped 0.86</p>
{_curve_svg(calibration.get("curve") or {})}
<p>Threshold meaningful on this score scale:
<strong>{"yes" if calibration.get("threshold_meaningful_on_this_scale") else "no"}</strong>.
{
        ""
        if calibration.get("threshold_meaningful_on_this_scale")
        else (
            "0.86 is the shipped DINOv2 cosine gate. This host ranked with "
            "the cheap visual fallback, so the line is the policy point, "
            "not a fit on this histogram."
        )
    }
</p>
</section>

<section>
<h2>Operational cost</h2>
<p>Wall per campaign: {_esc(operational.get("wall_seconds_per_campaign"))}s ·
fetches per campaign: {_esc(operational.get("fetches_per_campaign"))} ·
cache hit rate: {_esc(operational.get("cache_hit_rate"))} ·
images/s: {_esc(operational.get("images_per_second"))}</p>
<p>{_esc(operational.get("note"))}</p>
</section>

{adv}

<section>
<h2>Not computed</h2>
<ul>{missing}</ul>
</section>

<section>
<h2>What this benchmark does not cover</h2>
<ul>{limits}</ul>
</section>
</main>
</body>
</html>
"""
