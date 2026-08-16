"""Bounded response sizes, redirect chains, and decompression."""

from __future__ import annotations

from searcher.core.errors import ErrorClass, SearcherError

DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_PAGES = 50
# Refuse a body that expands more than this vs Content-Length.
MAX_DECOMPRESSION_RATIO = 50
MIN_LENGTH_FOR_RATIO = 1024


class ResponseTooLarge(SearcherError):
    def __init__(self, message: str, *, bytes_seen: int) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.NETWORK,
            details={"bytes_seen": str(bytes_seen)},
        )
        self.bytes_seen = bytes_seen


class RedirectLimitExceeded(SearcherError):
    def __init__(self, message: str, *, hops: int) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.NETWORK,
            details={"hops": str(hops)},
        )
        self.hops = hops


class DecompressionBomb(SearcherError):
    def __init__(self, message: str, *, declared: int, actual: int) -> None:
        super().__init__(
            message,
            error_class=ErrorClass.MALFORMED_CONTENT,
            details={"declared": str(declared), "actual": str(actual)},
        )


def check_byte_budget(seen: int, ceiling: int) -> None:
    if seen > ceiling:
        raise ResponseTooLarge(
            f"response exceeded {ceiling} bytes",
            bytes_seen=seen,
        )


def check_redirect_budget(hops: int, ceiling: int) -> None:
    if hops > ceiling:
        raise RedirectLimitExceeded(
            f"redirect chain exceeded {ceiling} hops",
            hops=hops,
        )


def check_decompression(declared_length: int | None, actual: int) -> None:
    if declared_length is None or declared_length < MIN_LENGTH_FOR_RATIO:
        return
    if actual > declared_length * MAX_DECOMPRESSION_RATIO:
        raise DecompressionBomb(
            "decompressed body exceeded safe expansion ratio",
            declared=declared_length,
            actual=actual,
        )
