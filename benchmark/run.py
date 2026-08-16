"""One command: uv run python -m benchmark.run --all"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .buckets import run_buckets
from .calibration import run_calibration
from .evidence import render_board
from .hostinfo import run_identity
from .paths import EVIDENCE_BOARD_PATH, SPLIT_MANIFEST
from .receipt import COMMAND, DOES_NOT_COVER, adversarial_finding, write_artifacts
from .retrieval import run_retrieval
from .splits import HELD_OUT, assert_no_leakage, load_canonical_splits, write_split_manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Held-out Searcher benchmark. Measures; does not tune."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run retrieval, buckets, calibration, and write every artifact.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.all:
        parser.print_help()
        print("\nRequired: --all", file=sys.stderr)
        return 2

    write_split_manifest()
    splits = load_canonical_splits()
    assert_no_leakage(splits.calibration_ids, splits.held_out_ids)

    retrieval = run_retrieval(splits, split=HELD_OUT)
    buckets = run_buckets(splits, split=HELD_OUT)
    calibration = run_calibration(splits, retrieval.scorer)
    identity = run_identity()
    from .operational import assemble_operational

    operational = assemble_operational(retrieval, buckets)
    not_computed = list(retrieval.not_computed) + list(buckets.not_computed)
    board = render_board(
        splits=splits,
        retrieval=retrieval,
        buckets=buckets,
        calibration=calibration,
        operational=operational,
        identity=identity,
        not_computed=not_computed,
        does_not_cover=DOES_NOT_COVER,
        adversarial=adversarial_finding(),
    )
    path = write_artifacts(
        splits=splits,
        retrieval=retrieval,
        buckets=buckets,
        calibration=calibration,
        board_html=board,
    )
    print(COMMAND)
    print(f"receipt: {path}")
    print(f"evidence: {EVIDENCE_BOARD_PATH}")
    print(f"splits: {SPLIT_MANIFEST}")
    print(f"retrieval overall: {retrieval.as_payload()['overall']}")
    print(f"false Real: {buckets.as_payload()['false_real']['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
