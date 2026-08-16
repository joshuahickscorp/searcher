"""End-to-end reference + hypothesis + query wave through the campaign controller."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from searcher.campaigns.controller import CampaignController
from searcher.core.config import Settings
from searcher.evidence.content_store import ContentStore
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate
from searcher.workers.reference.pipeline import create_reference_campaign, run_reference_query_wave


def _write(path: Path, label: str, size: tuple[int, int]) -> None:
    image = Image.new("RGB", size, (22, 22, 24))
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 30, size[0] - 20, size[1] - 20), fill=(14, 14, 16), outline=(80, 80, 70))
    draw.text((8, 6), label, fill=(230, 230, 220))
    image.save(path, format="PNG")


def test_pipeline_writes_report_and_competing_hypotheses(tmp_path: Path) -> None:
    settings = Settings.from_env(data_root=tmp_path)
    settings.ensure_data_root()
    db = Database(settings.db_path)
    migrate(db)
    store = ContentStore(settings.data_root, disk_margin_bytes=1024, max_object_bytes=5_000_000)
    controller = CampaignController(db, store, settings)
    images = [
        tmp_path / "a.png",
        tmp_path / "b.png",
        tmp_path / "c.png",
    ]
    _write(images[0], "LAT", (480, 300))
    _write(images[1], "MED", (460, 310))
    _write(images[2], "REAR", (300, 420))
    try:
        search_id = create_reference_campaign(
            controller,
            image_paths=images,
            text="Dior Homme General Army Trainer 07",
            tags=["Hedi Slimane", "2007", "black", "low-top"],
            settings=settings,
        )
        result = run_reference_query_wave(controller, search_id, images, settings=settings)
        assert result["hypotheses"] >= 2
        assert result["queries"] >= 6
        report = Path(str(result["report_html"]))
        assert report.is_file()
        html = report.read_text(encoding="utf-8")
        assert "Reference analysis" in html
        assert "Hypotheses" in html
        json_report = Path(str(result["report_json"]))
        assert json_report.is_file()
        campaign = controller.get(search_id)
        assert campaign.state.value == "PLANNING_QUERIES"
        hyps = controller.repos.list_hypotheses(search_id)
        assert len(hyps) >= 2
        queries = controller.repos.list_queries(search_id)
        langs = {q.language for q in queries}
        assert {"en", "ja", "ko", "zh", "fr", "it", "ru"} <= langs
    finally:
        db.close()
