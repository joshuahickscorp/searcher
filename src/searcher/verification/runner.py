"""Run the listing-page verification pass and attach the record."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from searcher.contracts.enums import (
    EvidencePolarity,
    ExtractionMethod,
    FactClass,
    SourceOutcome,
    VerificationVerdict,
)
from searcher.contracts.models import (
    BucketDecision,
    ListingCandidate,
    SourceManifest,
    VerificationRecord,
)
from searcher.core.errors import BudgetExceeded, CancelledError
from searcher.core.ids import new_id, sha256_hex
from searcher.core.time import utc_now
from searcher.evidence.lineage import raw_lineage
from searcher.evidence.records import EvidenceRecord
from searcher.sources.adapters.generic_page import GenericPageAdapter
from searcher.sources.challenge import is_challenge_block
from searcher.sources.fetch_modes import Escalator, FetchedDocument
from searcher.verification.compare import compare_fields, statements_for
from searcher.verification.extract import extract_structured, from_adapter_parse


def _method_of(payload: dict[str, Any] | None) -> ExtractionMethod | None:
    if not payload:
        return None
    raw = payload.get("extraction_method")
    if raw is None:
        return None
    try:
        return ExtractionMethod(str(raw))
    except ValueError:
        return ExtractionMethod.UNKNOWN


def _parse_with_adapter(adapter: object, doc: FetchedDocument) -> dict[str, Any] | None:
    parse = getattr(adapter, "parse", None)
    if not callable(parse):
        return None
    try:
        listings = parse(doc)
    except Exception:
        return None
    if not listings:
        return None
    raw = listings[0]
    payload = getattr(raw, "payload", None)
    if not isinstance(payload, dict):
        return None
    return from_adapter_parse(payload)


def extract_from_document(
    doc: FetchedDocument,
    *,
    adapter: object | None = None,
) -> dict[str, Any] | None:
    html = doc.body.decode("utf-8", errors="replace")
    url = doc.final_url or doc.result.url
    structured = extract_structured(html, url)
    if structured:
        return structured
    if adapter is not None:
        return _parse_with_adapter(adapter, doc)
    fallback = GenericPageAdapter()
    return _parse_with_adapter(fallback, doc)


def apply_record(candidate: ListingCandidate, record: VerificationRecord) -> ListingCandidate:
    support, contradictions, missing = statements_for(record)
    explanation = candidate.explanation.model_copy(
        update={
            "support": list(candidate.explanation.support) + support,
            "contradictions": list(candidate.explanation.contradictions) + contradictions,
            "missing_evidence": list(candidate.explanation.missing_evidence) + missing,
            "last_checked_at": record.checked_at,
        }
    )
    return candidate.model_copy(
        update={
            "verification": record,
            "last_checked_at": record.checked_at,
            "explanation": explanation,
        }
    )


def merge_verification(
    decision: BucketDecision, candidate: ListingCandidate
) -> BucketDecision:
    record = candidate.verification
    if record is None:
        return decision
    support, contradictions, missing = statements_for(record)
    explanation = decision.explanation.model_copy(
        update={
            "support": list(decision.explanation.support) + support,
            "contradictions": list(decision.explanation.contradictions) + contradictions,
            "missing_evidence": list(decision.explanation.missing_evidence) + missing,
            "last_checked_at": record.checked_at,
        }
    )
    return decision.model_copy(update={"explanation": explanation})


def _evidence_for(
    search_id: str,
    record: VerificationRecord,
    candidate: ListingCandidate,
) -> list[EvidenceRecord]:
    rows: list[EvidenceRecord] = []
    polarity_map = {
        VerificationVerdict.AGREES: EvidencePolarity.SUPPORTING,
        VerificationVerdict.DISAGREES: EvidencePolarity.CONTRADICTORY,
        VerificationVerdict.ABSENT: EvidencePolarity.MISSING,
    }
    for item in record.fields:
        if item.verdict is VerificationVerdict.UNCHECKED:
            # No evidence row at all: we learned nothing about this candidate,
            # and a candidate must not be marked down for a fetch we could not
            # complete.
            continue
        digest = sha256_hex(
            f"{candidate.candidate_id}:{item.field}:{item.verdict}:{item.reason}".encode()
        )
        identity = item.field in {"title", "seller"}
        rows.append(
            EvidenceRecord(
                evidence_id=new_id(),
                search_id=search_id,
                content_digest=digest,
                family_id=f"verification:{item.field}",
                polarity=polarity_map[item.verdict],
                fact_class=FactClass.EXTRACTED,
                accepted=True,
                lineage=raw_lineage(
                    input_digests=list(candidate.source_evidence),
                    process="listing_verification",
                ),
                created_at=item.checked_at,
                label=f"verification.{item.field}.{item.verdict.value}",
                hard=identity and item.verdict is VerificationVerdict.DISAGREES,
                notes=[item.reason],
            )
        )
    return rows


def _blocked_payload_note(doc: FetchedDocument) -> str:
    note = doc.result.classification_note or doc.result.outcome.value
    if is_challenge_block(doc.result.classification_note, doc.result.error_class):
        return f"blocked by challenge ({note})"
    return f"listing page not usable ({note})"


def verify_candidate(
    candidate: ListingCandidate,
    manifest: SourceManifest,
    escalator: Escalator,
    *,
    search_id: str,
    adapter: object | None = None,
    repos: Any | None = None,
) -> ListingCandidate:
    """Re-open the listing, extract structured fields, record agreement."""
    now = utc_now()
    try:
        doc = escalator.fetch(
            candidate.canonical_url,
            manifest,
            source_id=manifest.source_id,
            allow_render=True,
            skip_cache=True,
        )
    except BudgetExceeded:
        record = VerificationRecord(
            candidate_id=candidate.candidate_id,
            url=candidate.canonical_url,
            checked_at=now,
            fields=compare_fields(
                candidate,
                None,
                checked_at=now,
                extraction_method=None,
                fetch_note="budget exhausted before verification fetch",
                page_read=False,
            ),
            fetch_outcome=SourceOutcome.UNMEASURABLE,
            classification_note="budget exhausted",
        )
        return apply_record(candidate, record)
    except CancelledError:
        raise
    except Exception as exc:
        record = VerificationRecord(
            candidate_id=candidate.candidate_id,
            url=candidate.canonical_url,
            checked_at=now,
            fields=compare_fields(
                candidate,
                None,
                checked_at=now,
                extraction_method=None,
                fetch_note=str(exc),
                page_read=False,
            ),
            fetch_outcome=SourceOutcome.NETWORK_FAILED,
            classification_note=str(exc),
        )
        return apply_record(candidate, record)

    now = utc_now()
    usable = doc.result.outcome is SourceOutcome.SEARCHED_MATCHES_FOUND
    payload = extract_from_document(doc, adapter=adapter) if usable else None
    note = None if usable else _blocked_payload_note(doc)
    record = VerificationRecord(
        candidate_id=candidate.candidate_id,
        url=candidate.canonical_url,
        checked_at=now,
        fields=compare_fields(
            candidate,
            payload,
            checked_at=now,
            extraction_method=_method_of(payload),
            fetch_note=note,
            page_read=usable,
        ),
        extraction_method=_method_of(payload),
        fetch_outcome=doc.result.outcome,
        classification_note=doc.result.classification_note,
    )
    updated = apply_record(candidate, record)
    if repos is not None:
        for evidence in _evidence_for(search_id, record, updated):
            repos.insert_evidence(evidence)
        repos.upsert_candidate(search_id, updated)
    return updated


def verify_candidates(
    search_id: str,
    candidates: list[ListingCandidate],
    escalator: Escalator,
    resolve: Callable[[str], object],
    manifest_of: Callable[[object], SourceManifest],
    *,
    repos: Any | None = None,
) -> list[ListingCandidate]:
    updated: list[ListingCandidate] = []
    for candidate in candidates:
        try:
            adapter = resolve(candidate.source_adapter)
            manifest = manifest_of(adapter)
        except Exception:
            updated.append(candidate)
            continue
        try:
            fresh = verify_candidate(
                candidate,
                manifest,
                escalator,
                search_id=search_id,
                adapter=adapter,
                repos=repos,
            )
        except BudgetExceeded:
            updated.append(candidate)
            seen = {item.candidate_id for item in updated}
            updated.extend(item for item in candidates if item.candidate_id not in seen)
            return updated
        updated.append(fresh)
    return updated
