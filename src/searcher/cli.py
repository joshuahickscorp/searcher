"""Inspection CLI. Human-readable by default; --json for machines."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.events import list_events
from searcher.campaigns.resume import reconstruct
from searcher.campaigns.runner import FixtureRunner
from searcher.core.config import Settings
from searcher.core.errors import SearcherError
from searcher.evidence.content_store import ContentStore
from searcher.receipts.types import typed_from_payload
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate
from searcher.workers.reference.pipeline import create_reference_campaign, run_reference_query_wave


def _session(settings: Settings) -> tuple[Database, ContentStore, CampaignController]:
    settings.ensure_data_root()
    db = Database(settings.db_path)
    migrate(db, settings.migrations_dir)
    store = ContentStore(
        settings.data_root,
        disk_margin_bytes=settings.disk_margin_bytes,
        max_object_bytes=settings.max_object_bytes,
    )
    controller = CampaignController(db, store, settings)
    return db, store, controller


def _print(data: object, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True, default=str))
        return
    if isinstance(data, str):
        print(data)
        return
    print(json.dumps(data, indent=2, sort_keys=True, default=str))


def cmd_db_migrate(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    settings.ensure_data_root()
    applied = migrate(settings.db_path, settings.migrations_dir)
    if args.json:
        _print({"db": str(settings.db_path), "applied": applied}, as_json=True)
    else:
        print(f"database: {settings.db_path}")
        if applied:
            print("applied: " + ", ".join(applied))
        else:
            print("applied: (none, already current)")
    return 0


def cmd_campaign_create(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    db, store, controller = _session(settings)
    try:
        runner = FixtureRunner(controller, step_delay=settings.step_delay_seconds)
        intent = runner.create(args.fixture)
        payload = {"search_id": intent.search_id, "fixture": args.fixture, "state": "CREATED"}
        if args.json:
            _print(payload, as_json=True)
        else:
            print(f"search_id: {intent.search_id}")
            print(f"fixture: {args.fixture}")
            print("state: CREATED")
        return 0
    finally:
        db.close()
        del store


def cmd_campaign_run(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    db, store, controller = _session(settings)
    try:
        runner = FixtureRunner(controller, step_delay=settings.step_delay_seconds)
        runner.run(args.search_id)
        campaign = controller.get(args.search_id)
        payload = {
            "search_id": args.search_id,
            "state": campaign.state.value,
            "state_version": campaign.state_version,
            "terminal_status": campaign.terminal_status.value if campaign.terminal_status else None,
        }
        if args.json:
            _print(payload, as_json=True)
        else:
            print(f"search_id: {args.search_id}")
            print(f"state: {campaign.state.value}")
            print(f"state_version: {campaign.state_version}")
        return 0
    finally:
        db.close()
        del store


def cmd_campaign_resume(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    db, store, controller = _session(settings)
    try:
        snapshot = reconstruct(controller.repos, args.search_id)
        runner = FixtureRunner(controller, step_delay=settings.step_delay_seconds)
        runner.resume(args.search_id)
        campaign = controller.get(args.search_id)
        payload = {
            "search_id": args.search_id,
            "resumed_from": snapshot.state.value,
            "state": campaign.state.value,
            "accepted_evidence": len(snapshot.accepted_evidence_ids),
        }
        if args.json:
            _print(payload, as_json=True)
        else:
            print(f"search_id: {args.search_id}")
            print(f"resumed_from: {snapshot.state.value}")
            print(f"state: {campaign.state.value}")
            print(f"accepted_evidence_restored: {len(snapshot.accepted_evidence_ids)}")
        return 0
    finally:
        db.close()
        del store


def cmd_campaign_cancel(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    db, store, controller = _session(settings)
    try:
        campaign = controller.cancel(args.search_id)
        payload = {"search_id": args.search_id, "state": campaign.state.value}
        _print(
            payload if args.json else f"search_id: {args.search_id}\nstate: {campaign.state.value}",
            as_json=args.json,
        )
        return 0
    finally:
        db.close()
        del store


def _show_payload(controller: CampaignController, search_id: str) -> dict[str, Any]:
    campaign = controller.get(search_id)
    snapshot = reconstruct(controller.repos, search_id)
    results = controller.repos.list_results(search_id)
    counts = {"real": 0, "possibly_real": 0, "hidden": 0}
    for row in results:
        bucket = str(row["public_bucket"])
        counts[bucket] = counts.get(bucket, 0) + 1
    usage = controller.usage(search_id)
    return {
        "search_id": search_id,
        "state": campaign.state.value,
        "state_version": campaign.state_version,
        "terminal_status": campaign.terminal_status.value if campaign.terminal_status else None,
        "terminal_reason": campaign.terminal_reason,
        "hypotheses": len(snapshot.active_hypotheses),
        "completed_queries": len(snapshot.completed_queries),
        "source_cursors": snapshot.source_cursors,
        "fetched_pages": len(snapshot.fetched_pages),
        "normalized_candidates": len(snapshot.normalized_candidates),
        "accepted_evidence": len(snapshot.accepted_evidence_ids),
        "results": counts,
        "budget_used": usage.snapshot()["committed"],
        "last_checkpoint": snapshot.last_checkpoint.label if snapshot.last_checkpoint else None,
    }


def cmd_campaign_show(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    db, store, controller = _session(settings)
    try:
        payload = _show_payload(controller, args.search_id)
        if args.json:
            _print(payload, as_json=True)
            return 0
        print(f"Campaign {payload['search_id']}")
        print(f"  state: {payload['state']}  version={payload['state_version']}")
        print(f"  terminal: {payload['terminal_status']} ({payload['terminal_reason']})")
        print(f"  hypotheses: {payload['hypotheses']}")
        print(f"  fetched_pages: {payload['fetched_pages']}")
        print(f"  candidates: {payload['normalized_candidates']}")
        print(f"  accepted_evidence: {payload['accepted_evidence']}")
        results = payload["results"]
        print(
            f"  results: Real={results.get('real', 0)} "
            f"Possibly Real={results.get('possibly_real', 0)} "
            f"Hidden={results.get('hidden', 0)}"
        )
        print(f"  last_checkpoint: {payload['last_checkpoint']}")
        print(f"  budget committed: {payload['budget_used']}")
        return 0
    finally:
        db.close()
        del store


def cmd_campaign_events(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    db, store, controller = _session(settings)
    try:
        events = list_events(controller.repos, args.search_id)
        rows = [e.model_dump(mode="json") for e in events]
        if args.json:
            _print(rows, as_json=True)
            return 0
        for event in events:
            err = f" error={event.error}" if event.error else ""
            print(
                f"{event.timestamp.isoformat()}  v{event.state_version}  "
                f"{event.event_name}  {event.actor}{err}"
            )
        return 0
    finally:
        db.close()
        del store


def cmd_campaign_budget(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    db, store, controller = _session(settings)
    try:
        usage = controller.usage(args.search_id)
        payload = usage.snapshot()
        if args.json:
            _print(payload, as_json=True)
            return 0
        sealed = payload["sealed"]
        committed = payload["committed"]
        print(f"Campaign {args.search_id} budget")
        print(f"  sealed digest: {sealed['digest']}")
        for key in ("pages", "images", "bytes", "sources", "model_calls"):
            print(f"  {key}: {committed.get(key, 0)}")
        return 0
    finally:
        db.close()
        del store


def cmd_receipt_verify(args: argparse.Namespace) -> int:
    path = Path(args.path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    receipt = typed_from_payload(payload)
    ok = receipt.verify()
    result = {
        "path": str(path),
        "receipt_id": receipt.receipt_id,
        "receipt_type": receipt.receipt_type,
        "ok": ok,
        "digest": receipt.digest,
    }
    if args.json:
        _print(result, as_json=True)
    else:
        print(f"path: {path}")
        print(f"receipt_id: {receipt.receipt_id}")
        print(f"type: {receipt.receipt_type}")
        print("verify: PASS" if ok else "verify: FAIL")
    return 0 if ok else 2


def cmd_capabilities(args: argparse.Namespace) -> int:
    import time

    from searcher.integrations.visionmcp.probe import donor_status, probe_timed

    started = time.perf_counter()
    report, elapsed = probe_timed()
    wall = time.perf_counter() - started
    payload = {
        "elapsed_seconds": elapsed,
        "wall_seconds": wall,
        "donor": donor_status(),
        "capabilities": [r.model_dump(mode="json") for r in report.capabilities],
    }
    if args.json:
        _print(payload, as_json=True)
        return 0
    print(f"probe_seconds: {elapsed:.4f}")
    print(f"donor: {payload['donor']}")
    for rec in report.capabilities:
        flag = "yes" if rec.available else "no"
        print(f"  {rec.name.value:24} available={flag:3}  {rec.notes}")
    return 0


def cmd_reference_analyze(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    db, store, controller = _session(settings)
    try:
        images = [Path(p) for p in args.image]
        search_id = create_reference_campaign(
            controller,
            image_paths=images,
            text=args.text,
            tags=list(args.tag or []),
            settings=settings,
        )
        result = run_reference_query_wave(controller, search_id, images, settings=settings)
        if args.json:
            _print(result, as_json=True)
        else:
            print(f"search_id: {result['search_id']}")
            print(f"state: {result['state']}")
            print(f"hypotheses: {result['hypotheses']}")
            print(f"queries: {result['queries']}")
            print(f"donor_invoked: {result['donor_invoked']}")
            print(f"promotion_blocked: {result['promotion_blocked']}")
            print(f"report: {result['report_html']}")
        return 0
    finally:
        db.close()
        del store


def cmd_store_stat(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    settings.ensure_data_root()
    store = ContentStore(
        settings.data_root,
        disk_margin_bytes=settings.disk_margin_bytes,
        max_object_bytes=settings.max_object_bytes,
    )
    stat = store.stat()
    payload = {
        "root": stat.root,
        "object_count": stat.object_count,
        "byte_count": stat.byte_count,
        "zones": stat.zones,
        "disk_free": stat.disk_free,
        "disk_margin": stat.disk_margin,
    }
    if args.json:
        _print(payload, as_json=True)
    else:
        print(f"root: {stat.root}")
        print(f"objects: {stat.object_count} ({stat.byte_count} bytes)")
        print(f"zones: {stat.zones}")
        print(f"disk_free: {stat.disk_free}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="searcher", description="Searcher inspection CLI")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="group", required=True)

    campaign = sub.add_parser("campaign", help="campaign commands")
    csub = campaign.add_subparsers(dest="command", required=True)

    create = csub.add_parser("create", help="create a fixture campaign")
    create.add_argument("--fixture", required=True)
    create.set_defaults(func=cmd_campaign_create)

    run = csub.add_parser("run", help="run a campaign")
    run.add_argument("search_id")
    run.set_defaults(func=cmd_campaign_run)

    show = csub.add_parser("show", help="show a campaign")
    show.add_argument("search_id")
    show.set_defaults(func=cmd_campaign_show)

    events = csub.add_parser("events", help="list campaign events")
    events.add_argument("search_id")
    events.set_defaults(func=cmd_campaign_events)

    resume = csub.add_parser("resume", help="resume a campaign from disk")
    resume.add_argument("search_id")
    resume.set_defaults(func=cmd_campaign_resume)

    cancel = csub.add_parser("cancel", help="cancel a campaign")
    cancel.add_argument("search_id")
    cancel.set_defaults(func=cmd_campaign_cancel)

    budget = csub.add_parser("budget", help="show sealed budget usage")
    budget.add_argument("search_id")
    budget.set_defaults(func=cmd_campaign_budget)

    receipt = sub.add_parser("receipt", help="receipt commands")
    rsub = receipt.add_subparsers(dest="command", required=True)
    verify = rsub.add_parser("verify", help="verify a stored receipt")
    verify.add_argument("path")
    verify.set_defaults(func=cmd_receipt_verify)

    store = sub.add_parser("store", help="object store commands")
    ssub = store.add_subparsers(dest="command", required=True)
    stat = ssub.add_parser("stat", help="store statistics")
    stat.set_defaults(func=cmd_store_stat)

    dbp = sub.add_parser("db", help="database commands")
    dsub = dbp.add_subparsers(dest="command", required=True)
    migrate_cmd = dsub.add_parser("migrate", help="apply SQL migrations")
    migrate_cmd.set_defaults(func=cmd_db_migrate)

    caps = sub.add_parser("capabilities", help="light capability probe")
    caps.set_defaults(func=cmd_capabilities)

    reference = sub.add_parser("reference", help="reference analysis")
    rsub = reference.add_subparsers(dest="command", required=True)
    analyze = rsub.add_parser("analyze", help="ingest images and compile queries")
    analyze.add_argument("--image", action="append", required=True, dest="image")
    analyze.add_argument("--text", default=None)
    analyze.add_argument("--tag", action="append", default=[])
    analyze.set_defaults(func=cmd_reference_analyze)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return int(args.func(args))
    except SearcherError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(exc), "class": exc.error_class.value}))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyError as exc:
        print(f"error: unknown campaign {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
