"""Host-aware concurrent I/O that never exceeds a host's own rate policy."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor

from searcher.sources.classify import host_of


def host_key(url: str) -> str:
    return host_of(url) or url


def concurrent_cap(policy: object | None, default: int = 1) -> int:
    raw = getattr(policy, "concurrent", default) if policy is not None else default
    try:
        return max(1, int(raw or default))
    except (TypeError, ValueError):
        return max(1, default)


def map_by_host[T, R](
    items: Sequence[T],
    fn: Callable[[T], R],
    *,
    host_of_item: Callable[[T], str],
    cap_of: Callable[[T], int] | None = None,
    default_cap: int = 1,
) -> list[R]:
    """Apply ``fn`` to every item.

    Items that share a host stay within that host's concurrency cap (default 1).
    Different hosts overlap. A single item or a single host at cap 1 stays on
    the calling thread so tests and the warm path pay no pool overhead.
    """
    if not items:
        return []
    if len(items) == 1:
        return [fn(items[0])]

    groups: dict[str, list[tuple[int, T]]] = defaultdict(list)
    for index, item in enumerate(items):
        groups[host_of_item(item)].append((index, item))

    only_host = next(iter(groups))
    first_cap = default_cap
    if cap_of is not None:
        first_cap = max(1, int(cap_of(groups[only_host][0][1]) or default_cap))
    if len(groups) == 1 and first_cap <= 1:
        return [fn(item) for item in items]

    results: list[R | None] = [None] * len(items)
    errors: list[BaseException] = []

    def run_one(index: int, item: T) -> None:
        if errors:
            return
        try:
            results[index] = fn(item)
        except BaseException as exc:  # noqa: BLE001 — surface the first worker failure
            errors.append(exc)

    def run_group(group: list[tuple[int, T]], cap: int) -> None:
        if cap <= 1:
            for index, item in group:
                run_one(index, item)
            return
        workers = min(cap, len(group))
        with ThreadPoolExecutor(max_workers=workers) as inner:
            futs = [inner.submit(run_one, index, item) for index, item in group]
            for fut in futs:
                fut.result()

    with ThreadPoolExecutor(max_workers=max(1, len(groups))) as pool:
        futs = []
        for group in groups.values():
            cap = default_cap
            if cap_of is not None:
                cap = max(1, int(cap_of(group[0][1]) or default_cap))
            futs.append(pool.submit(run_group, group, cap))
        for fut in futs:
            fut.result()

    if errors:
        raise errors[0]
    filled: list[R] = []
    for slot in results:
        if slot is None:
            raise RuntimeError("host-aware map left a result slot empty")
        filled.append(slot)
    return filled
