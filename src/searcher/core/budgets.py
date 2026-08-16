"""Sealed campaign budget and atomic usage accounting (§3.9, §9.1)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from searcher.core.errors import BudgetExceeded
from searcher.core.ids import canonical_dumps, new_id, sha256_hex

DIMENSIONS = (
    "wall_seconds",
    "sources",
    "pages",
    "browser_pages",
    "images",
    "model_calls",
    "bytes",
    "retries",
    "storage",
)

_INT_DIMS = frozenset(DIMENSIONS)


@dataclass(frozen=True, slots=True)
class Budget:
    """Declared ceilings. Immutable once constructed; seal() to bind a campaign."""

    wall_seconds: int
    source_limit: int
    page_limit: int
    browser_page_limit: int
    image_limit: int
    model_call_limit: int
    byte_limit: int
    monetary_limit: Decimal | None = None
    retry_limit: int = 8
    storage_limit: int = 1_000_000_000
    per_host_rate: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "wall_seconds",
            "source_limit",
            "page_limit",
            "browser_page_limit",
            "image_limit",
            "model_call_limit",
            "byte_limit",
            "retry_limit",
            "storage_limit",
        ):
            value = getattr(self, name)
            if int(value) < 0:
                raise ValueError(f"{name} must be >= 0")
        if self.monetary_limit is not None and self.monetary_limit < 0:
            raise ValueError("monetary_limit must be >= 0")

    def ceiling(self, dimension: str) -> int | Decimal:
        mapping: dict[str, int | Decimal | None] = {
            "wall_seconds": self.wall_seconds,
            "sources": self.source_limit,
            "pages": self.page_limit,
            "browser_pages": self.browser_page_limit,
            "images": self.image_limit,
            "model_calls": self.model_call_limit,
            "bytes": self.byte_limit,
            "retries": self.retry_limit,
            "storage": self.storage_limit,
            "monetary": self.monetary_limit,
        }
        if dimension not in mapping:
            raise KeyError(dimension)
        value = mapping[dimension]
        if value is None:
            return Decimal("Infinity")
        return value

    def seal(self) -> SealedBudget:
        payload = {
            "wall_seconds": self.wall_seconds,
            "source_limit": self.source_limit,
            "page_limit": self.page_limit,
            "browser_page_limit": self.browser_page_limit,
            "image_limit": self.image_limit,
            "model_call_limit": self.model_call_limit,
            "byte_limit": self.byte_limit,
            "monetary_limit": (
                str(self.monetary_limit) if self.monetary_limit is not None else None
            ),
            "retry_limit": self.retry_limit,
            "storage_limit": self.storage_limit,
            "per_host_rate": dict(self.per_host_rate),
        }
        digest = sha256_hex(canonical_dumps(payload).encode("utf-8"))
        return SealedBudget(budget=self, digest=digest)

    def to_dict(self) -> dict[str, Any]:
        return {
            "wall_seconds": self.wall_seconds,
            "source_limit": self.source_limit,
            "page_limit": self.page_limit,
            "browser_page_limit": self.browser_page_limit,
            "image_limit": self.image_limit,
            "model_call_limit": self.model_call_limit,
            "byte_limit": self.byte_limit,
            "monetary_limit": (
                str(self.monetary_limit) if self.monetary_limit is not None else None
            ),
            "retry_limit": self.retry_limit,
            "storage_limit": self.storage_limit,
            "per_host_rate": dict(self.per_host_rate),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Budget:
        monetary = data.get("monetary_limit")
        return cls(
            wall_seconds=int(data["wall_seconds"]),
            source_limit=int(data["source_limit"]),
            page_limit=int(data["page_limit"]),
            browser_page_limit=int(data["browser_page_limit"]),
            image_limit=int(data["image_limit"]),
            model_call_limit=int(data["model_call_limit"]),
            byte_limit=int(data["byte_limit"]),
            monetary_limit=Decimal(str(monetary)) if monetary is not None else None,
            retry_limit=int(data.get("retry_limit", 8)),
            storage_limit=int(data.get("storage_limit", 1_000_000_000)),
            per_host_rate=dict(data.get("per_host_rate") or {}),
        )

    @classmethod
    def fixture_default(cls) -> Budget:
        return cls(
            wall_seconds=300,
            source_limit=8,
            page_limit=50,
            browser_page_limit=0,
            image_limit=40,
            model_call_limit=0,
            byte_limit=50_000_000,
            monetary_limit=None,
            retry_limit=4,
            storage_limit=100_000_000,
        )


@dataclass(frozen=True, slots=True)
class SealedBudget:
    """A Budget bound to a digest. Ceilings cannot be raised after sealing."""

    budget: Budget
    digest: str

    def ceiling(self, dimension: str) -> int | Decimal:
        return self.budget.ceiling(dimension)

    def to_dict(self) -> dict[str, Any]:
        payload = self.budget.to_dict()
        payload["digest"] = self.digest
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SealedBudget:
        digest = str(data["digest"])
        budget = Budget.from_dict(data)
        sealed = budget.seal()
        if sealed.digest != digest:
            raise ValueError("sealed budget digest does not match payload")
        return sealed


@dataclass(slots=True)
class Reservation:
    reservation_id: str
    dimensions: dict[str, int]
    monetary: Decimal
    committed: bool = False
    released: bool = False


class BudgetUsage:
    """Mutable usage against a sealed budget. reserve/commit are atomic."""

    def __init__(self, sealed: SealedBudget, *, search_id: str | None = None) -> None:
        self.sealed = sealed
        self.search_id = search_id
        self._lock = threading.Lock()
        self._committed: dict[str, int] = {name: 0 for name in _INT_DIMS}
        self._reserved: dict[str, int] = {name: 0 for name in _INT_DIMS}
        self._committed_monetary = Decimal("0")
        self._reserved_monetary = Decimal("0")
        self._open: dict[str, Reservation] = {}

    def used(self, dimension: str) -> int | Decimal:
        if dimension == "monetary":
            return self._committed_monetary + self._reserved_monetary
        return self._committed[dimension] + self._reserved[dimension]

    def committed(self, dimension: str) -> int | Decimal:
        if dimension == "monetary":
            return self._committed_monetary
        return self._committed[dimension]

    def would_exceed(
        self,
        *,
        wall_seconds: int = 0,
        sources: int = 0,
        pages: int = 0,
        browser_pages: int = 0,
        images: int = 0,
        model_calls: int = 0,
        bytes: int = 0,
        retries: int = 0,
        storage: int = 0,
        monetary: Decimal | int | str | None = None,
    ) -> str | None:
        """Return the first dimension that would cross its ceiling, else None.

        This is the hard refusal guard. Property tests fail if it is removed.
        """
        requested: dict[str, int] = {
            "wall_seconds": wall_seconds,
            "sources": sources,
            "pages": pages,
            "browser_pages": browser_pages,
            "images": images,
            "model_calls": model_calls,
            "bytes": bytes,
            "retries": retries,
            "storage": storage,
        }
        for name, amount in requested.items():
            if amount < 0:
                raise ValueError(f"{name} request must be >= 0")
            if amount == 0:
                continue
            ceiling = self.sealed.ceiling(name)
            projected = int(self.used(name)) + amount
            if projected > int(ceiling):
                return name
        if monetary is not None:
            extra = Decimal(str(monetary))
            if extra < 0:
                raise ValueError("monetary request must be >= 0")
            if extra > 0:
                ceiling = self.sealed.ceiling("monetary")
                if isinstance(ceiling, Decimal) and ceiling.is_infinite():
                    return None
                projected_m = self._committed_monetary + self._reserved_monetary + extra
                if projected_m > Decimal(str(ceiling)):
                    return "monetary"
        return None

    def reserve(
        self,
        *,
        wall_seconds: int = 0,
        sources: int = 0,
        pages: int = 0,
        browser_pages: int = 0,
        images: int = 0,
        model_calls: int = 0,
        bytes: int = 0,
        retries: int = 0,
        storage: int = 0,
        monetary: Decimal | int | str | None = None,
    ) -> Reservation:
        extra_m = Decimal(str(monetary)) if monetary is not None else Decimal("0")
        with self._lock:
            offender = self.would_exceed(
                wall_seconds=wall_seconds,
                sources=sources,
                pages=pages,
                browser_pages=browser_pages,
                images=images,
                model_calls=model_calls,
                bytes=bytes,
                retries=retries,
                storage=storage,
                monetary=extra_m,
            )
            if offender is not None:
                raise BudgetExceeded(
                    f"sealed budget ceiling would be crossed on {offender}",
                    dimension=offender,
                    search_id=self.search_id,
                )
            dims = {
                "wall_seconds": wall_seconds,
                "sources": sources,
                "pages": pages,
                "browser_pages": browser_pages,
                "images": images,
                "model_calls": model_calls,
                "bytes": bytes,
                "retries": retries,
                "storage": storage,
            }
            for name, amount in dims.items():
                self._reserved[name] += amount
            self._reserved_monetary += extra_m
            reservation = Reservation(
                reservation_id=new_id(),
                dimensions=dims,
                monetary=extra_m,
            )
            self._open[reservation.reservation_id] = reservation
            return reservation

    def commit(self, reservation: Reservation) -> None:
        with self._lock:
            held = self._open.get(reservation.reservation_id)
            if held is None or held.committed or held.released:
                raise BudgetExceeded(
                    "reservation is not open",
                    dimension="reservation",
                    search_id=self.search_id,
                )
            for name, amount in held.dimensions.items():
                self._reserved[name] -= amount
                self._committed[name] += amount
            self._reserved_monetary -= held.monetary
            self._committed_monetary += held.monetary
            held.committed = True
            reservation.committed = True
            del self._open[reservation.reservation_id]

    def release(self, reservation: Reservation) -> None:
        with self._lock:
            held = self._open.get(reservation.reservation_id)
            if held is None or held.committed or held.released:
                raise BudgetExceeded(
                    "reservation is not open",
                    dimension="reservation",
                    search_id=self.search_id,
                )
            for name, amount in held.dimensions.items():
                self._reserved[name] -= amount
            self._reserved_monetary -= held.monetary
            held.released = True
            reservation.released = True
            del self._open[reservation.reservation_id]

    def consume(
        self,
        *,
        wall_seconds: int = 0,
        sources: int = 0,
        pages: int = 0,
        browser_pages: int = 0,
        images: int = 0,
        model_calls: int = 0,
        bytes: int = 0,
        retries: int = 0,
        storage: int = 0,
        monetary: Decimal | int | str | None = None,
    ) -> None:
        """Reserve and immediately commit. Convenience for already-spent work."""
        reservation = self.reserve(
            wall_seconds=wall_seconds,
            sources=sources,
            pages=pages,
            browser_pages=browser_pages,
            images=images,
            model_calls=model_calls,
            bytes=bytes,
            retries=retries,
            storage=storage,
            monetary=monetary,
        )
        self.commit(reservation)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "committed": dict(self._committed),
                "reserved": dict(self._reserved),
                "committed_monetary": str(self._committed_monetary),
                "reserved_monetary": str(self._reserved_monetary),
                "sealed": self.sealed.to_dict(),
            }

    def restore(self, payload: dict[str, Any]) -> None:
        with self._lock:
            committed = payload.get("committed") or {}
            reserved = payload.get("reserved") or {}
            for name in _INT_DIMS:
                self._committed[name] = int(committed.get(name, 0))
                self._reserved[name] = int(reserved.get(name, 0))
            self._committed_monetary = Decimal(str(payload.get("committed_monetary", "0")))
            self._reserved_monetary = Decimal(str(payload.get("reserved_monetary", "0")))

    def never_exceeds_ceiling(self) -> bool:
        """Invariant used by property tests."""
        for name in _INT_DIMS:
            if int(self.used(name)) > int(self.sealed.ceiling(name)):
                return False
        ceiling = self.sealed.ceiling("monetary")
        return not (
            isinstance(ceiling, Decimal)
            and not ceiling.is_infinite()
            and self.used("monetary") > ceiling
        )
