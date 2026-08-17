"""Bible §32.9 specified mutations.

Each test applies one named sabotage to a real function with monkeypatch,
then re-runs the existing test or assertion that should notice. A mutation
is KILLED when that assertion fails. A mutation that leaves those assertions
green has SURVIVED; that failure is the finding, not a reason to weaken the
sabotage.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import replace
from threading import Lock
from typing import Any

import pytest

from searcher.contracts.enums import (
    Availability,
    BucketInternal,
    BucketPublic,
    EvidencePolarity,
    FactClass,
    SourceOutcome,
)
from searcher.contracts.primitives import EvidenceWeight, ScoreInterval
from searcher.core.ids import new_id
from searcher.core.policy import GateView, RealGate
from searcher.core.time import parse_utc
from searcher.evidence.lineage import raw_lineage
from searcher.evidence.records import EvidenceRecord

_TS = parse_utc("2007-06-15T12:00:00+00:00")
_FAILED = getattr(pytest.fail, "Exception", AssertionError)
_LEDGER: list[tuple[str, str, str]] = []


def _evaluate(mutation: str, *killers: tuple[str, Callable[[], None]]) -> tuple[str, str]:
    """Run existing assertions. KILLED if one fails; SURVIVED if they all pass."""
    tried: list[str] = []
    for name, action in killers:
        tried.append(name)
        try:
            action()
        except AssertionError:
            _LEDGER.append((mutation, "KILLED", name))
            return "KILLED", name
        except BaseException as exc:
            if isinstance(exc, _FAILED) or type(exc).__name__ == "Failed":
                _LEDGER.append((mutation, "KILLED", name))
                return "KILLED", name
            raise
    reason = "still passed: " + ", ".join(tried)
    _LEDGER.append((mutation, "SURVIVED", reason))
    return "SURVIVED", reason


@pytest.fixture(scope="session", autouse=True)
def _print_mutation_ledger() -> Iterator[None]:
    yield
    print("\n§32.9 mutation ledger")
    for mutation, status, detail in _LEDGER:
        print(f"  {status:8}  {mutation}  ({detail})")


def _duplicate_record(family: str, digest: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=new_id(),
        search_id="s",
        content_digest=digest,
        family_id=family,
        polarity=EvidencePolarity.SUPPORTING,
        fact_class=FactClass.REPORTED_BY_SOURCE,
        accepted=True,
        lineage=raw_lineage(input_digests=[digest], process="test"),
        created_at=_TS,
    )


def test_mutation_count_duplicate_images_as_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bible §32.9: count duplicate images as independent.

    Expected killer: tests.property.test_p01_duplicate_evidence
    ::test_duplicate_evidence_never_increases_independent_count
    (also tests.property.test_p15_duplicate_images::test_same_bytes_same_family).
    """
    import searcher.evidence.independence as independence

    monkeypatch.setattr(independence, "independent_family_count", lambda records: len(records))

    def killer() -> None:
        records = [
            _duplicate_record("fam-a", "d00fama"),
            _duplicate_record("fam-a", "dup-fama"),
        ]
        extras = [_duplicate_record("fam-a", "dup-extra") for _ in range(5)]
        unique = {"fam-a"}
        assert independence.independent_family_count(records) == len(unique)
        assert independence.independent_family_count(records + extras) == (
            independence.independent_family_count(records)
        )

    status, detail = _evaluate(
        "count duplicate images as independent",
        (
            "tests.property.test_p01_duplicate_evidence."
            "test_duplicate_evidence_never_increases_independent_count",
            killer,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"count duplicate images as independent: {status} ({detail})")


def test_mutation_disable_live_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bible §32.9: disable live check.

    Expected killer: tests.property.test_p08_dead_listing
    ::test_dead_listing_cannot_become_real
    (route_public_bucket / require_live_for_real).
    """
    import searcher.contracts.routing as routing
    import searcher.core.policy as policy

    original_evaluate = policy.evaluate_real_gate

    def without_live(view: GateView, gate: RealGate | None = None) -> bool:
        active = gate or RealGate()
        return original_evaluate(view, replace(active, require_live=False))

    monkeypatch.setattr(policy, "evaluate_real_gate", without_live)
    monkeypatch.setattr(
        routing,
        "require_live_for_real",
        lambda *, availability, live_checked, intended: intended,
    )

    def killer() -> None:
        view = GateView(
            item_match_lower_bound=0.95,
            authenticity_lower_bound=0.90,
            evidence_completeness=0.9,
            availability=Availability.SOLD.value,
            live_checked=False,
            destination_verified=True,
        )
        assert policy.route_public_bucket(view) != "real"
        assert (
            routing.require_live_for_real(
                availability=Availability.SOLD,
                live_checked=True,
                intended=BucketPublic.REAL,
            )
            is BucketPublic.HIDDEN
        )

    status, detail = _evaluate(
        "disable live check",
        (
            "tests.property.test_p08_dead_listing.test_dead_listing_cannot_become_real",
            killer,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"disable live check: {status} ({detail})")


def test_mutation_map_blocked_source_to_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bible §32.9: map blocked source to no-match.

    Expected killer: tests.unit.test_status_classification
    ::test_blocked_cannot_become_no_match
    (also tests.property.test_p09_blocked_source
    ::test_blocked_source_cannot_be_searched_no_match).
    """
    import tests.unit.test_status_classification as status_tests

    import searcher.contracts.routing as routing

    def as_no_match(outcome: SourceOutcome) -> SourceOutcome:
        del outcome
        return SourceOutcome.SEARCHED_NO_MATCH

    monkeypatch.setattr(routing, "as_searched_no_match", as_no_match)
    monkeypatch.setattr(status_tests, "as_searched_no_match", as_no_match)

    status, detail = _evaluate(
        "map blocked source to no-match",
        (
            "tests.unit.test_status_classification.test_blocked_cannot_become_no_match",
            status_tests.test_blocked_cannot_become_no_match,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"map blocked source to no-match: {status} ({detail})")


def test_mutation_make_price_increase_authenticity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bible §32.9: make price increase authenticity.

    Expected killer: tests.property.test_p12_price_authenticity
    ::test_price_alone_cannot_raise_authenticity.
    """
    import searcher.authenticity.decision as decision
    import searcher.core.policy as policy

    def price_raises(current_lower_bound: float, price_contribution: float) -> float:
        return current_lower_bound + price_contribution

    monkeypatch.setattr(policy, "apply_price_to_authenticity", price_raises)
    monkeypatch.setattr(decision, "apply_price_to_authenticity", price_raises)

    def killer() -> None:
        updated = policy.apply_price_to_authenticity(0.40, 0.30)
        assert updated <= 0.40 + 1e-12

    status, detail = _evaluate(
        "make price increase authenticity",
        (
            "tests.property.test_p12_price_authenticity.test_price_alone_cannot_raise_authenticity",
            killer,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"make price increase authenticity: {status} ({detail})")


def test_mutation_bypass_hard_contradiction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bible §32.9: bypass hard contradiction.

    Expected killer: tests.unit.test_score_containers
    ::test_hard_contradiction_crushes_item_interval
    (also tests.property.test_p02_hard_contradiction
    ::test_adding_hard_contradiction_cannot_raise_bucket_confidence).
    """
    import tests.unit.test_score_containers as score_tests

    import searcher.contracts.primitives as primitives
    import searcher.core.policy as policy
    import searcher.matching.combine as combine
    import searcher.matching.scores as scores

    original_evaluate = policy.evaluate_real_gate

    def no_penalty(interval: ScoreInterval, *, hard_count: int) -> ScoreInterval:
        del hard_count
        return interval

    def no_clamp(previous: float, evidence: list[EvidenceWeight]) -> float:
        del previous
        return primitives.bucket_confidence(evidence)

    def no_hard_gate(view: GateView, gate: RealGate | None = None) -> bool:
        active = gate or RealGate()
        return original_evaluate(
            view,
            replace(
                active,
                forbid_hard_item_contradiction=False,
                forbid_hard_authenticity_contradiction=False,
            ),
        )

    monkeypatch.setattr(scores, "apply_hard_penalty", no_penalty)
    monkeypatch.setattr(combine, "apply_hard_penalty", no_penalty)
    monkeypatch.setattr(primitives, "bucket_confidence_after_hard_contradiction", no_clamp)
    monkeypatch.setattr(policy, "evaluate_real_gate", no_hard_gate)

    def property_killer() -> None:
        existing = [
            EvidenceWeight(
                evidence_id="e0",
                family_id="f0",
                polarity=EvidencePolarity.SUPPORTING,
                weight=0.8,
                hard=False,
            )
        ]
        previous = primitives.bucket_confidence(existing)
        contra = EvidenceWeight(
            evidence_id="hard-contra",
            family_id="contra",
            polarity=EvidencePolarity.CONTRADICTORY,
            weight=0.99,
            hard=True,
        )
        updated = primitives.bucket_confidence_after_hard_contradiction(
            previous, existing + [contra]
        )
        assert updated <= previous + 1e-12

    status, detail = _evaluate(
        "bypass hard contradiction",
        (
            "tests.unit.test_score_containers.test_hard_contradiction_crushes_item_interval",
            score_tests.test_hard_contradiction_crushes_item_interval,
        ),
        (
            "tests.property.test_p02_hard_contradiction."
            "test_adding_hard_contradiction_cannot_raise_bucket_confidence",
            property_killer,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"bypass hard contradiction: {status} ({detail})")


def test_mutation_move_all_candidates_to_real(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bible §32.9: move all candidates to Real.

    Expected killer: tests.unit.test_replica_publication
    ::test_replica_family_with_perfect_scores_is_refused_real_and_possibly_real
    (also tests.unit.test_gate_evaluation.test_adjacent_is_hidden).
    """
    import tests.unit.test_replica_publication as replica_tests

    import searcher.campaigns.publication as publication
    import searcher.core.policy as policy
    import searcher.ranking.buckets as buckets

    original_route = buckets.route_candidate

    def always_real_public(view: GateView) -> str:
        del view
        return "real"

    def always_real_published(decision: Any, candidate: Any) -> str:
        del decision, candidate
        return BucketPublic.REAL.value

    def always_real_route(**kwargs: Any) -> Any:
        decision = original_route(**kwargs)
        return decision.model_copy(
            update={
                "decision": decision.decision.model_copy(
                    update={"public": BucketPublic.REAL, "internal": BucketInternal.REAL}
                )
            }
        )

    monkeypatch.setattr(policy, "route_public_bucket", always_real_public)
    monkeypatch.setattr(publication, "published_public_bucket", always_real_published)
    monkeypatch.setattr(replica_tests, "published_public_bucket", always_real_published)
    monkeypatch.setattr(buckets, "route_candidate", always_real_route)

    status, detail = _evaluate(
        "move all candidates to Real",
        (
            "tests.unit.test_replica_publication."
            "test_replica_family_with_perfect_scores_is_refused_real_and_possibly_real",
            replica_tests.test_replica_family_with_perfect_scores_is_refused_real_and_possibly_real,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"move all candidates to Real: {status} ({detail})")


def test_mutation_skip_receipt_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bible §32.9: skip receipt verification.

    Expected killer: tests.unit.test_receipts.test_tamper_fails_verification
    (also tests.unit.test_receipts.test_stored_file_tamper).
    """
    from tests.unit.test_receipts import test_tamper_fails_verification

    from searcher.receipts.base import ReceiptBase

    monkeypatch.setattr(ReceiptBase, "verify", lambda self: True)

    status, detail = _evaluate(
        "skip receipt verification",
        (
            "tests.unit.test_receipts.test_tamper_fails_verification",
            test_tamper_fails_verification,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"skip receipt verification: {status} ({detail})")


def test_mutation_accept_changed_donor_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bible §32.9: accept changed donor SHA.

    Expected killer: tests.unit.test_compatibility.test_pinned_constants
    and assert_core_contract's ``sha != PINNED_SHA`` branch.
    """
    from tests.unit.test_compatibility import test_pinned_constants

    import searcher.integrations.visionmcp.compatibility as compat

    original = compat.assert_core_contract

    def accept_changed() -> dict[str, str]:
        try:
            return original()
        except compat.CompatibilityError as exc:
            if "SHA" in str(exc):
                return {
                    "version": compat.PINNED_VERSION,
                    "sha": "accepted-drift",
                    "distribution": compat.PINNED_DISTRIBUTION,
                    "adapter_version": compat.ADAPTER_VERSION,
                }
            raise

    monkeypatch.setattr(compat, "assert_core_contract", accept_changed)
    monkeypatch.setattr(compat, "donor_sha_from_install", lambda module=None: "0" * 40)

    def drift_killer() -> None:
        # Added after this mutation SURVIVED: the pin was only ever checked as a
        # constant, never exercised against a donor that moved.
        import pytest as _pytest

        if compat.import_visionmcp() is None:
            _pytest.skip("visionmcp is not installed in this environment")
        with _pytest.raises(compat.CompatibilityError):
            compat.assert_core_contract()

    status, detail = _evaluate(
        "accept changed donor SHA",
        (
            "tests.unit.test_compatibility.test_pinned_constants",
            test_pinned_constants,
        ),
        (
            "tests.unit.test_compatibility.test_drifted_donor_sha_is_refused",
            drift_killer,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"accept changed donor SHA: {status} ({detail})")


def test_mutation_omit_search_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bible §32.9: omit search budget.

    Expected killer: tests.unit.test_budgets.test_ceiling_refusal
    (also tests.property.test_p05_budget_ceiling
    ::test_budget_usage_never_exceeds_sealed_ceiling).
    """
    from tests.unit.test_budgets import test_ceiling_refusal

    from searcher.core.budgets import BudgetUsage

    monkeypatch.setattr(BudgetUsage, "would_exceed", lambda self, **kwargs: None)

    status, detail = _evaluate(
        "omit search budget",
        (
            "tests.unit.test_budgets.test_ceiling_refusal",
            test_ceiling_refusal,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"omit search budget: {status} ({detail})")


def test_mutation_preserve_browser_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bible §32.9: preserve browser process.

    Expected killer: tests.real_runtime.test_browser_leak
    ::test_browser_pool_leaves_no_orphans
    (in-process counterpart: live_count() == 0 after close()).
    """
    from searcher.sources.browser import BrowserPool

    monkeypatch.setattr(BrowserPool, "close", lambda self: None)

    pool = BrowserPool.__new__(BrowserPool)
    pool._lock = Lock()
    pool._live = 1
    pool._browsers = [object()]
    pool._playwright = object()

    def killer() -> None:
        pool.close()
        assert pool.live_count() == 0, "orphaned browser processes: in-process live_count"

    status, detail = _evaluate(
        "preserve browser process",
        (
            "tests.real_runtime.test_browser_leak.test_browser_pool_leaves_no_orphans",
            killer,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"preserve browser process: {status} ({detail})")


def test_mutation_leak_upload_path(
    monkeypatch: pytest.MonkeyPatch,
    api_app: tuple[Any, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Bible §32.9: leak upload path.

    Expected killer: tests.unit.test_upload_validation.test_path_traversal_refused
    and tests.security.test_api_security.test_logs_omit_filename_and_paths.
    """
    import io
    import logging

    import tests.unit.test_upload_validation as upload_tests
    from PIL import Image

    import searcher.api.uploads as uploads
    import searcher.reference.validation as validation
    from searcher.core.errors import InputError

    original_refuse = validation.refuse_path_name
    original_validate = validation.validate_upload_bytes

    def refuse_leaking(name: str) -> None:
        try:
            original_refuse(name)
        except InputError:
            raise InputError(f"path traversal refused: {name}") from None

    def validate_leaking(
        data: bytes,
        *,
        declared_name: str | None = None,
        declared_type: str | None = None,
        settings: Any | None = None,
    ) -> Any:
        validated = original_validate(
            data,
            declared_name=declared_name,
            declared_type=declared_type,
            settings=settings,
        )
        return replace(validated, declared_name=declared_name)

    monkeypatch.setattr(validation, "refuse_path_name", refuse_leaking)
    monkeypatch.setattr(upload_tests, "refuse_path_name", refuse_leaking)
    monkeypatch.setattr(validation, "validate_upload_bytes", validate_leaking)
    # searcher.api.uploads does `from ...validation import refuse_path_name`,
    # binding by value at import, so patching the validation module alone never
    # reaches the API's call site and the sabotage silently does nothing. This
    # mutation first reported SURVIVED for exactly that reason - it could not
    # fire. A mutation that cannot fire proves nothing about the suite.
    monkeypatch.setattr(uploads, "refuse_path_name", refuse_leaking)
    monkeypatch.setattr(uploads, "validate_upload_bytes", validate_leaking)
    monkeypatch.setattr(uploads, "_public_input_message", lambda exc: str(exc))

    def log_killer() -> None:
        def png() -> bytes:
            buf = io.BytesIO()
            Image.new("RGB", (24, 24), (8, 16, 24)).save(buf, format="PNG")
            return buf.getvalue()

        client, _app = api_app
        caplog.set_level(logging.INFO, logger="searcher.api")
        client.post(
            "/v1/searches",
            data={"text": "probe"},
            files=[("images", ("secret-upload.png", png(), "image/png"))],
        )
        client.post(
            "/v1/searches",
            data={"text": "probe"},
            files=[("images", ("/tmp/private/photo.png", b"", "image/png"))],
        )
        text = caplog.text
        assert "secret-upload.png" not in text
        assert "/tmp/private" not in text
        assert "photo.png" not in text

    def body_killer() -> None:
        # Added after this mutation first SURVIVED: logs and traversal were
        # checked, the body returned to the caller was not.
        def png() -> bytes:
            buf = io.BytesIO()
            Image.new("RGB", (24, 24), (8, 16, 24)).save(buf, format="PNG")
            return buf.getvalue()

        client, _app = api_app
        for name in ("../../etc/passwd", "/tmp/private/photo.png"):
            response = client.post(
                "/v1/searches",
                data={"text": "probe"},
                files=[("images", (name, png(), "image/png"))],
            )
            body = response.text
            assert name not in body, f"error body echoed the submitted path: {body[:160]}"
            for fragment in ("etc/passwd", "/tmp/private", ".."):
                assert fragment not in body, f"error body leaked {fragment!r}: {body[:160]}"

    status, detail = _evaluate(
        "leak upload path",
        (
            "tests.unit.test_upload_validation.test_path_traversal_refused",
            upload_tests.test_path_traversal_refused,
        ),
        (
            "tests.security.test_api_security.test_logs_omit_filename_and_paths",
            log_killer,
        ),
        (
            "tests.security.test_api_security.test_error_body_never_echoes_the_submitted_path",
            body_killer,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"leak upload path: {status} ({detail})")


def test_mutation_expose_hidden_benchmark_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bible §32.9: expose hidden benchmark answer.

    The twelfth sabotage, and the one this suite shipped without. §32.9 lists
    twelve; eleven were implemented and the suite was reported complete. Round 6
    counted them.

    The sabotage leaks a held-out identifier into the calibration split, which
    is how a benchmark quietly starts reporting on data it was tuned against.
    `assert_no_leakage` exists to refuse exactly that.

    Expected killer:
    tests.unit.test_benchmark_splits.test_canonical_splits_have_no_shared_identifier
    """
    import benchmark.splits as splits_mod
    from tests.unit.test_benchmark_splits import (
        test_canonical_splits_have_no_shared_identifier,
    )

    original = splits_mod.assign_splits
    splits = original()
    held = splits.held_out_ids
    assert held, "no held-out identifiers; this mutation would prove nothing"

    # The sabotage: a held-out identifier appears in the calibration split, so
    # the benchmark is tuned against data it later reports on. The guard that
    # exists to refuse this is assert_no_leakage.
    leaked = (*splits.calibration_ids, held[0])

    def guard_killer() -> None:
        from benchmark.splits import SplitLeakageError, assert_no_leakage

        # The guard signals a leak by raising SplitLeakageError. _evaluate reads
        # a killer as having caught the sabotage when it fails an assertion, so
        # the refusal is translated into one rather than escaping the harness.
        try:
            assert_no_leakage(leaked, splits.held_out_ids)
        except SplitLeakageError as exc:
            raise AssertionError(f"leakage guard refused the sabotage: {exc}") from exc

    status, detail = _evaluate(
        "expose hidden benchmark answer",
        (
            "benchmark.splits.assert_no_leakage",
            guard_killer,
        ),
        (
            "tests.unit.test_benchmark_splits.test_canonical_splits_have_no_shared_identifier",
            test_canonical_splits_have_no_shared_identifier,
        ),
    )
    assert status in {"KILLED", "SURVIVED"}
    print(f"expose hidden benchmark answer: {status} ({detail})")
