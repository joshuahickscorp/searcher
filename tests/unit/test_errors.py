"""Error taxonomy carries a §30.3 class."""

from __future__ import annotations

from searcher.core.errors import (
    BudgetExceeded,
    ErrorClass,
    IllegalTransition,
    InvariantViolation,
    PathEscapeError,
    SearcherError,
)


def test_every_exception_has_class() -> None:
    err = SearcherError("x", error_class=ErrorClass.PARSE)
    assert err.error_class is ErrorClass.PARSE
    assert "PARSE" in str(err)


def test_subclasses() -> None:
    assert BudgetExceeded("x", dimension="pages").error_class is ErrorClass.BUDGET
    assert (
        IllegalTransition("x", source="A", target="B").error_class is ErrorClass.INTERNAL_INVARIANT
    )
    assert PathEscapeError("x").error_class is ErrorClass.STORAGE
    assert InvariantViolation("x").error_class is ErrorClass.INTERNAL_INVARIANT


def test_taxonomy_is_complete() -> None:
    expected = {
        "INPUT",
        "POLICY",
        "NETWORK",
        "RATE_LIMIT",
        "ACCESS_BLOCK",
        "AUTH_REQUIRED",
        "PARSE",
        "MALFORMED_CONTENT",
        "MODEL",
        "BROWSER",
        "STORAGE",
        "DATABASE",
        "TIMEOUT",
        "BUDGET",
        "CANCELLED",
        "INTERNAL_INVARIANT",
    }
    assert {item.value for item in ErrorClass} == expected
