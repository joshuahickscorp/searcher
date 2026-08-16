"""§30.3 error taxonomy and the exception hierarchy that carries it."""

from __future__ import annotations

from enum import StrEnum


class ErrorClass(StrEnum):
    INPUT = "INPUT"
    POLICY = "POLICY"
    NETWORK = "NETWORK"
    RATE_LIMIT = "RATE_LIMIT"
    ACCESS_BLOCK = "ACCESS_BLOCK"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    PARSE = "PARSE"
    MALFORMED_CONTENT = "MALFORMED_CONTENT"
    MODEL = "MODEL"
    BROWSER = "BROWSER"
    STORAGE = "STORAGE"
    DATABASE = "DATABASE"
    TIMEOUT = "TIMEOUT"
    BUDGET = "BUDGET"
    CANCELLED = "CANCELLED"
    INTERNAL_INVARIANT = "INTERNAL_INVARIANT"


class SearcherError(Exception):
    """Every raised Searcher error carries a §30.3 class."""

    def __init__(
        self,
        message: str,
        *,
        error_class: ErrorClass,
        search_id: str | None = None,
        details: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_class = error_class
        self.search_id = search_id
        self.details = details or {}

    def __str__(self) -> str:
        base = f"[{self.error_class}] {super().__str__()}"
        if self.search_id:
            return f"{base} (search_id={self.search_id})"
        return base


class BudgetExceeded(SearcherError):
    def __init__(self, message: str, *, dimension: str, search_id: str | None = None) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.BUDGET,
            search_id=search_id,
            details={"dimension": dimension},
        )
        self.dimension = dimension


class IllegalTransition(SearcherError):
    def __init__(
        self,
        message: str,
        *,
        source: str,
        target: str,
        search_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.INTERNAL_INVARIANT,
            search_id=search_id,
            details={"source": source, "target": target},
        )
        self.source = source
        self.target = target


class StaleStateVersion(SearcherError):
    def __init__(
        self,
        message: str,
        *,
        search_id: str,
        expected: int,
        actual: int | None = None,
    ) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.DATABASE,
            search_id=search_id,
            details={"expected": str(expected), "actual": str(actual)},
        )
        self.expected = expected
        self.actual = actual


class PathEscapeError(SearcherError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_class=ErrorClass.STORAGE)


class StoragePressureError(SearcherError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_class=ErrorClass.STORAGE)


class ReceiptVerificationError(SearcherError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_class=ErrorClass.INTERNAL_INVARIANT)


class IdempotencyConflict(SearcherError):
    def __init__(self, message: str, *, search_id: str, key: str) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.INTERNAL_INVARIANT,
            search_id=search_id,
            details={"idempotency_key": key},
        )


class CrossCampaignAccessError(SearcherError):
    def __init__(self, message: str, *, search_id: str, other_id: str | None = None) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.POLICY,
            search_id=search_id,
            details={"other_id": other_id or ""},
        )


class InvariantViolation(SearcherError):
    def __init__(self, message: str, *, search_id: str | None = None) -> None:
        super().__init__(message, error_class=ErrorClass.INTERNAL_INVARIANT, search_id=search_id)


class NaiveDatetimeError(SearcherError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_class=ErrorClass.INPUT)


class InputError(SearcherError):
    def __init__(self, message: str, *, search_id: str | None = None) -> None:
        super().__init__(message, error_class=ErrorClass.INPUT, search_id=search_id)


class CancelledError(SearcherError):
    def __init__(self, message: str, *, search_id: str | None = None) -> None:
        super().__init__(message, error_class=ErrorClass.CANCELLED, search_id=search_id)


class PolicyBlocked(SearcherError):
    def __init__(
        self, message: str, *, search_id: str | None = None, url: str | None = None
    ) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.POLICY,
            search_id=search_id,
            details={"url": url or ""},
        )
        self.url = url


class AccessBlocked(SearcherError):
    def __init__(
        self,
        message: str,
        *,
        search_id: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.ACCESS_BLOCK,
            search_id=search_id,
            details={"http_status": str(http_status) if http_status is not None else ""},
        )
        self.http_status = http_status


class SsrfBlocked(SearcherError):
    def __init__(self, message: str, *, url: str | None = None) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.POLICY,
            details={"url": url or ""},
        )
        self.url = url


class RateLimited(SearcherError):
    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        search_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.RATE_LIMIT,
            search_id=search_id,
            details={"retry_after": str(retry_after) if retry_after is not None else ""},
        )
        self.retry_after = retry_after
