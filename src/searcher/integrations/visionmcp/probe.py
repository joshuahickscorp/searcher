"""§5.13 light capability probe. No model weights, no browser, no worker spawn."""

from __future__ import annotations

import os
import shutil
import time
from typing import Any

from searcher.core.capabilities import (
    CapabilityName,
    CapabilityRecord,
    CapabilityRegistry,
    CapabilityReport,
    CapabilityStability,
)
from searcher.integrations.visionmcp.compatibility import (
    PINNED_SHA,
    PINNED_VERSION,
    CompatibilityError,
    assert_report_shape,
    donor_version,
    import_visionmcp,
    visionmcp_enabled,
)
from searcher.integrations.visionmcp.schema_map import map_donor_capability_row


def _pillow_available() -> bool:
    try:
        import PIL  # noqa: F401

        return True
    except ImportError:
        return False


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _donor_core_report() -> tuple[dict[str, Any] | None, str | None]:
    """Call capabilities_report. Must stay millisecond-cheap."""
    if not visionmcp_enabled():
        return None, "SEARCHER_VISIONMCP disabled"
    pkg = import_visionmcp()
    if pkg is None:
        return None, "visionmcp not importable"
    try:
        from visionmcp.capabilities import (
            capabilities_report,
            core_doctor_report,
        )
    except ImportError as exc:
        return None, f"visionmcp.capabilities missing: {exc}"
    try:
        doctor = core_doctor_report(network_forbidden=True)
        report = capabilities_report(profile="core")
    except Exception as exc:  # pragma: no cover - donor must not throw
        return None, f"donor probe failed: {type(exc).__name__}"
    try:
        assert_report_shape(report)
    except CompatibilityError as exc:
        return None, str(exc)
    report["_doctor_ok"] = bool(doctor.get("ok"))
    report["_donor_version"] = donor_version(pkg)
    return report, None


def _record(
    name: CapabilityName,
    *,
    available: bool,
    stability: CapabilityStability,
    dependency: str | None,
    resource_cost: str,
    authority_ceiling: str,
    notes: str,
) -> CapabilityRecord:
    return CapabilityRecord(
        name=name,
        available=available,
        stability=stability,
        dependency=dependency,
        resource_cost=resource_cost,
        authority_ceiling=authority_ceiling,
        notes=notes,
    )


def probe_capabilities() -> CapabilityReport:
    """Health-check-safe probe for every §5.13 name."""
    donor_report, donor_error = _donor_core_report()
    pillow = _pillow_available()
    tesseract = _tesseract_available()
    mapped: dict[CapabilityName, CapabilityRecord] = {}
    if donor_report is not None:
        for bucket in ("available", "blocked", "experimental"):
            for row in donor_report.get(bucket) or []:
                if not isinstance(row, dict):
                    continue
                record = map_donor_capability_row(row)
                if record is not None:
                    mapped[record.name] = record

    records: list[CapabilityRecord] = []
    for name in CapabilityName:
        if name is CapabilityName.IMAGE_DECODE:
            donor_ok = mapped.get(name)
            available = pillow
            dep = "Pillow"
            notes = "Searcher-owned decode via Pillow."
            if donor_ok and donor_ok.available:
                notes += " VisionMCP inspect_image available (lazy)."
                dep = "Pillow+visionmcp.evidence.references"
            elif donor_error:
                notes += f" Donor inspect path unused ({donor_error})."
            records.append(
                _record(
                    name,
                    available=available,
                    stability=(
                        CapabilityStability.STABLE if available else CapabilityStability.UNAVAILABLE
                    ),
                    dependency=dep if available else None,
                    resource_cost="cpu-cheap",
                    authority_ceiling="OBSERVED-pixels" if available else "none",
                    notes=notes,
                )
            )
            continue
        if name is CapabilityName.OCR:
            records.append(
                _record(
                    name,
                    available=tesseract,
                    stability=(
                        CapabilityStability.STABLE if tesseract else CapabilityStability.UNAVAILABLE
                    ),
                    dependency="tesseract" if tesseract else None,
                    resource_cost="cpu-cheap",
                    authority_ceiling="EXTRACTED" if tesseract else "none",
                    notes=(
                        "Host tesseract via Searcher subprocess. "
                        "Output is EXTRACTED, never OBSERVED."
                        if tesseract
                        else "tesseract not on PATH; OCR lane blocked."
                    ),
                )
            )
            continue
        if name is CapabilityName.RECEIPT_VERIFY:
            records.append(
                _record(
                    name,
                    available=True,
                    stability=CapabilityStability.STABLE,
                    dependency="searcher.receipts",
                    resource_cost="cpu-cheap",
                    authority_ceiling="local-recompute",
                    notes=(
                        "Searcher hash-chained receipts verify by recomputation. "
                        "visionmcp.receipts.public is not imported (eager compiler/kernels)."
                    ),
                )
            )
            continue
        if name is CapabilityName.NEXT_VIEW:
            records.append(
                _record(
                    name,
                    available=True,
                    stability=CapabilityStability.STABLE,
                    dependency="searcher.reference",
                    resource_cost="cpu-cheap",
                    authority_ceiling="INFERRED-heuristic",
                    notes=(
                        "Searcher-owned missing-evidence heuristic. "
                        "Donor 3D next-view planner is deferred."
                    ),
                )
            )
            continue
        if name is CapabilityName.BROWSER_CAPTURE:
            donor = mapped.get(name)
            available = bool(donor and donor.available)
            records.append(
                _record(
                    name,
                    available=available,
                    stability=donor.stability if donor else CapabilityStability.UNAVAILABLE,
                    dependency="visionmcp[web]+chrome" if available else None,
                    resource_cost="medium-high (browser process)",
                    authority_ceiling="OBSERVED-browser" if available else "none",
                    notes=(
                        donor.notes
                        if donor
                        else "Browser capture requires the web extra; not used in this wave."
                    ),
                )
            )
            continue
        # Everything else is deferred or absent at this SHA.
        reasons = {
            CapabilityName.OBJECT_SEGMENTATION: (
                "ocular.segment deferred (classical GrabCut, not product parts). "
                "Searcher cheap silhouette is DIAGNOSTIC only."
            ),
            CapabilityName.DENSE_FEATURES: (
                "No learned backbone at pinned SHA. propose_dense_features is Canny/HOG. "
                "Searcher cheap descriptors are not dense features."
            ),
            CapabilityName.LOGO_DETECTION: "No logo detector at pinned SHA.",
            CapabilityName.LOCAL_CORRESPONDENCE: (
                "No SIFT/SuperPoint/LoFTR. Product correspondence is a later wave."
            ),
            CapabilityName.MATERIAL_ANALYSIS: (
                "Donor materials.* are renderer-parity kernels, not listing leather-vs-suede."
            ),
            CapabilityName.WORLD_STATE: (
                "Donor world models are scene entities. Searcher owns ProductHypothesisGraph."
            ),
        }
        records.append(
            _record(
                name,
                available=False,
                stability=CapabilityStability.UNAVAILABLE,
                dependency=None,
                resource_cost="none",
                authority_ceiling="none",
                notes=reasons.get(name, "unavailable at pinned SHA"),
            )
        )
    return CapabilityReport(capabilities=records)


class VisionMcpProbe:
    """CapabilityProbe implementation. Safe to call from GET /v1/health."""

    def probe(self, name: CapabilityName) -> CapabilityRecord:
        report = probe_capabilities()
        for record in report.capabilities:
            if record.name is name:
                return record
        return CapabilityRecord(
            name=name,
            available=False,
            stability=CapabilityStability.UNAVAILABLE,
            dependency=None,
            resource_cost="none",
            authority_ceiling="none",
            notes="unknown capability",
        )


def apply_probe(registry: CapabilityRegistry) -> CapabilityReport:
    report = probe_capabilities()
    for record in report.capabilities:
        registry.register(record)
    return report


def probe_timed() -> tuple[CapabilityReport, float]:
    started = time.perf_counter()
    report = probe_capabilities()
    elapsed = time.perf_counter() - started
    return report, elapsed


def donor_status() -> dict[str, Any]:
    pkg = import_visionmcp()
    return {
        "enabled": visionmcp_enabled(),
        "importable": pkg is not None,
        "version": donor_version(pkg),
        "pinned_version": PINNED_VERSION,
        "pinned_sha": PINNED_SHA,
        "pillow": _pillow_available(),
        "tesseract": _tesseract_available(),
        "privacy_mode": os.environ.get("SEARCHER_PRIVACY_MODE", "local"),
    }
