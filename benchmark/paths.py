"""Repository-relative locations for the benchmark."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
KIND_PACK = FIXTURES / "known_item_kind" / "pack.json"
KIND_IMAGES = FIXTURES / "known_item_kind" / "images"
HARD_NEGATIVES = FIXTURES / "hard_negatives"
SPLIT_MANIFEST = FIXTURES / "benchmark" / "splits.json"
ARTIFACTS = ROOT / "artifacts"
BENCHMARK_ARTIFACTS = ARTIFACTS / "benchmark"
RECEIPT_PATH = ARTIFACTS / "searcher-public-benchmark.receipt.json"
EVIDENCE_BOARD_PATH = BENCHMARK_ARTIFACTS / "evidence-board.html"
SPLIT_RECEIPT_PATH = BENCHMARK_ARTIFACTS / "splits.manifest.json"
ADVERSARIAL_RECEIPT = ARTIFACTS / "searcher-adversarial-recall.receipt.json"
CALIBRATION_RECEIPT = ARTIFACTS / "searcher-match-calibration.receipt.json"
PERFORMANCE_RECEIPT = ARTIFACTS / "searcher-performance.receipt.json"
