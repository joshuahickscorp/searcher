"""Bind Searcher to the pinned VisionMCP SHA. Fail loudly if the contract moved."""

from __future__ import annotations

import importlib
import inspect
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

PINNED_SHA = "18ee3c06d27f04937d1681dea5fa2650131e4b2a"
PINNED_VERSION = "0.8.0a2"
PINNED_DISTRIBUTION = "visionmcp-ocular"
ADAPTER_VERSION = "searcher-visionmcp-1"

# Donor symbols the adapter may call. Names and call signatures are the contract.
REQUIRED_CORE_SYMBOLS = (
    "visionmcp.capabilities:capabilities_report",
    "visionmcp.capabilities:core_doctor_report",
)
REQUIRED_IMAGING_SYMBOLS = ("visionmcp.evidence.references:inspect_image",)
OPTIONAL_HEAVY_SYMBOLS = (
    "visionmcp.perception.media:analyze_image",
    "visionmcp.comparison.images:silhouette_mask",
)

# capabilities_report keys observed at the pinned SHA.
REQUIRED_REPORT_KEYS = frozenset(
    {
        "available",
        "blocked",
        "experimental",
        "plugins",
        "blockers",
        "api_versions",
        "network",
        "authority",
    }
)


class CompatibilityError(RuntimeError):
    """The pinned donor no longer matches the audited contract."""


def visionmcp_enabled() -> bool:
    flag = os.environ.get("SEARCHER_VISIONMCP", "1").strip().lower()
    return flag not in {"0", "false", "off", "no"}


def import_visionmcp() -> Any | None:
    """Import the donor core package. Never imports torch / ocular / playwright."""
    if not visionmcp_enabled():
        return None
    try:
        return importlib.import_module("visionmcp")
    except ImportError:
        return None


def donor_version(module: Any | None = None) -> str | None:
    pkg = module if module is not None else import_visionmcp()
    if pkg is None:
        return None
    version = getattr(pkg, "__version__", None)
    return str(version) if version is not None else None


def donor_sha_from_install(module: Any | None = None) -> str | None:
    """Best-effort SHA of the installed tree. None if it is a wheel without git."""
    pkg = module if module is not None else import_visionmcp()
    if pkg is None:
        return None
    path = getattr(pkg, "__file__", None)
    if not path:
        return None
    here = Path(path).resolve().parent
    for candidate in (here, *here.parents):
        if candidate.name in {"site-packages", "dist-packages"}:
            break
        git_dir = candidate / ".git"
        if not git_dir.is_dir():
            continue
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1].strip()
            ref_path = git_dir / ref
            if ref_path.is_file():
                return ref_path.read_text(encoding="utf-8").strip()
        if len(head) >= 40:
            return head[:40]
    return None


def _load_symbol(dotted: str) -> Any:
    module_name, _, attr = dotted.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def _signature_ok(fn: Callable[..., Any], required: tuple[str, ...]) -> bool:
    params = inspect.signature(fn).parameters
    return all(name in params for name in required)


def assert_core_contract() -> dict[str, str]:
    """Raise CompatibilityError if the donor core ABI drifted from the pin."""
    pkg = import_visionmcp()
    if pkg is None:
        raise CompatibilityError(
            f"visionmcp is not importable; expected {PINNED_DISTRIBUTION}=={PINNED_VERSION} "
            f"@ {PINNED_SHA}"
        )
    version = donor_version(pkg)
    if version != PINNED_VERSION:
        raise CompatibilityError(
            f"visionmcp version moved: have {version!r}, pinned {PINNED_VERSION!r} @ {PINNED_SHA}"
        )
    sha = donor_sha_from_install(pkg)
    if sha is not None and sha != PINNED_SHA:
        raise CompatibilityError(f"visionmcp git SHA moved: have {sha}, pinned {PINNED_SHA}")
    for dotted in REQUIRED_CORE_SYMBOLS:
        try:
            symbol = _load_symbol(dotted)
        except (ImportError, AttributeError) as exc:
            raise CompatibilityError(f"donor contract missing {dotted}: {exc}") from exc
        if not callable(symbol):
            raise CompatibilityError(f"donor contract {dotted} is not callable")
    report_fn = _load_symbol("visionmcp.capabilities:capabilities_report")
    if not _signature_ok(report_fn, ("profile", "schema_bytes", "tool_names")):
        raise CompatibilityError("capabilities_report signature changed")
    doctor_fn = _load_symbol("visionmcp.capabilities:core_doctor_report")
    if not _signature_ok(doctor_fn, ("network_forbidden",)):
        raise CompatibilityError("core_doctor_report signature changed")
    return {
        "version": version or "",
        "sha": sha or "unverified-wheel",
        "distribution": PINNED_DISTRIBUTION,
        "adapter_version": ADAPTER_VERSION,
    }


def assert_imaging_contract() -> None:
    """Imaging symbols are optional at health-check time; required to call inspect."""
    for dotted in REQUIRED_IMAGING_SYMBOLS:
        try:
            symbol = _load_symbol(dotted)
        except (ImportError, AttributeError) as exc:
            raise CompatibilityError(f"donor imaging contract missing {dotted}: {exc}") from exc
        if not callable(symbol):
            raise CompatibilityError(f"donor imaging contract {dotted} is not callable")
    inspect_fn = _load_symbol("visionmcp.evidence.references:inspect_image")
    params = list(inspect.signature(inspect_fn).parameters)
    if not params or params[0] != "path":
        raise CompatibilityError("inspect_image(path) signature changed")


def capabilities_report_keys(report: dict[str, Any]) -> frozenset[str]:
    return frozenset(report)


def assert_report_shape(report: dict[str, Any]) -> None:
    missing = REQUIRED_REPORT_KEYS - set(report)
    if missing:
        raise CompatibilityError(f"capabilities_report keys moved; missing {sorted(missing)}")
