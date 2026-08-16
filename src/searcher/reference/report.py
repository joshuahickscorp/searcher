"""Local developer report. No user filenames or private paths."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from searcher.contracts.models import ItemHypothesis, QueryVariant, ReferenceAnalysis


def _esc(value: object) -> str:
    return html.escape(str(value))


def analysis_to_jsonable(
    analysis: ReferenceAnalysis,
    *,
    hypotheses: list[ItemHypothesis] | None = None,
    queries: list[QueryVariant] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "analysis": analysis.model_dump(mode="json"),
        "hypotheses": [item.model_dump(mode="json") for item in hypotheses or []],
        "queries": [item.model_dump(mode="json") for item in queries or []],
    }
    return payload


def render_html(
    analysis: ReferenceAnalysis,
    *,
    hypotheses: list[ItemHypothesis] | None = None,
    queries: list[QueryVariant] | None = None,
) -> str:
    rows = []
    for image in analysis.images:
        crops = "".join(
            f"<li>crop {_esc(c.crop_id[:8])} view={_esc(c.view_hypothesis.value)} "
            f"conf={c.confidence:.2f} region={_esc(c.region)}</li>"
            for c in image.derived.crops
        )
        ocr = "".join(
            f"<li class='{'inj' if o.injection_candidate else ''}'>"
            f"[{_esc(o.kind)}/{_esc(o.fact_class.value)}] {_esc(o.text)} "
            f"conf={o.confidence:.2f}</li>"
            for o in image.derived.ocr
        )
        quality = analysis.quality_map.get(image.reference_image_id)
        rows.append(
            f"<section><h3>image {_esc(image.reference_image_id)}</h3>"
            f"<p>digest={_esc(image.content_digest[:16])}… "
            f"{image.width}×{image.height} {_esc(image.media_type)}</p>"
            f"<p>quality weight={getattr(quality, 'weight', 0):.2f} "
            f"blur={getattr(quality, 'blur', 0):.2f} "
            f"usable={_esc(getattr(quality, 'usable_for', []))}</p>"
            f"<h4>crops</h4><ul>{crops or '<li>none</li>'}</ul>"
            f"<h4>ocr</h4><ul>{ocr or '<li>none</li>'}</ul></section>"
        )
    views = "".join(
        f"<li>{_esc(v.view.value)} conf={v.confidence:.2f} crop={_esc(v.crop_id[:8])}</li>"
        for v in analysis.view_inventory
    )
    parts = "".join(
        f"<li>{_esc(p.part)} conf={p.confidence:.2f}</li>" for p in analysis.part_inventory
    )
    clusters = (
        f"<p>primary {_esc(analysis.primary_cluster.relation)} "
        f"n={len(analysis.primary_cluster.image_ids)}</p>"
        + "".join(
            f"<p>alternate {_esc(c.relation)} n={len(c.image_ids)}</p>"
            for c in analysis.alternate_clusters
        )
    )
    hy_html = ""
    for hyp in hypotheses or []:
        hy_html += (
            f"<article><h4>{_esc(hyp.hypothesis_id[:8])} "
            f"{_esc(hyp.status.value)} post={hyp.posterior:.3f}</h4>"
            f"<p>category={_esc(hyp.category)} "
            f"brand={_esc(hyp.brand.value)} ({_esc(hyp.brand.fact_class.value)}) "
            f"model={_esc(hyp.model_name.value)} ({_esc(hyp.model_name.fact_class.value)}) "
            f"year={_esc(hyp.year.value)}</p>"
            f"<p>evidence={_esc(hyp.supporting_evidence)} "
            f"contradictions={_esc(hyp.contradictions)}</p></article>"
        )
    by_lang: dict[str, list[QueryVariant]] = {}
    for query in queries or []:
        by_lang.setdefault(query.language, []).append(query)
    q_html = ""
    for lang, items in sorted(by_lang.items()):
        q_html += f"<h4>{_esc(lang)} ({len(items)})</h4><ul>"
        for query in items:
            q_html += (
                f"<li>r{query.round} {_esc(query.query_type.value)} "
                f"gain={query.expected_gain:.3f} cost={query.cost_estimate:.2f} "
                f"{_esc(query.query_text)}</li>"
            )
        q_html += "</ul>"
    lanes = "".join(
        f"<li>{_esc(lane.name)} available={lane.available} blocked={lane.blocked} "
        f"{_esc(lane.reason)}</li>"
        for lane in analysis.lanes
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Searcher reference report</title>
<style>
body {{ font-family: sans-serif; max-width: 960px; margin: 2rem auto; }}
.inj {{ color: #a40; }}
section, article {{ border: 1px solid #ddd; padding: 0.8rem; margin: 0.8rem 0; }}
code {{ font-size: 0.9em; }}
</style></head><body>
<h1>Reference analysis</h1>
<p>search={_esc(analysis.search_id)} analysis={_esc(analysis.analysis_id)}</p>
<p>donor_invoked={analysis.donor_invoked} promotion_blocked={analysis.promotion_blocked}</p>
<h2>Clusters</h2>{clusters}
<h2>Images, crops, OCR</h2>{"".join(rows)}
<h2>Views</h2><ul>{views}</ul>
<h2>Parts</h2><ul>{parts}</ul>
<h2>Visual signature</h2>
<p>kind={_esc(analysis.visual_signature.descriptor_kind)}
learned={analysis.visual_signature.learned_embedding_available}</p>
<p>ocr terms: {_esc(analysis.visual_signature.ocr_terms)}</p>
<h2>Hypotheses</h2>{hy_html or "<p>none</p>"}
<h2>Query plan</h2>{q_html or "<p>none</p>"}
<h2>Lanes</h2><ul>{lanes}</ul>
</body></html>
"""


def write_report(
    directory: Path,
    analysis: ReferenceAnalysis,
    *,
    hypotheses: list[ItemHypothesis] | None = None,
    queries: list[QueryVariant] | None = None,
) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    payload = analysis_to_jsonable(analysis, hypotheses=hypotheses, queries=queries)
    json_path = directory / "report.json"
    html_path = directory / "report.html"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    html_path.write_text(
        render_html(analysis, hypotheses=hypotheses, queries=queries), encoding="utf-8"
    )
    return html_path, json_path
