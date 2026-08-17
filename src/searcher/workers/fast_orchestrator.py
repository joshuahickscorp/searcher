"""Orchestrator subclass: download listing images concurrently per host."""

from __future__ import annotations

from typing import Any

from searcher.campaigns.orchestrator import CampaignOrchestrator, _from_index_feed, layers_present
from searcher.contracts.enums import Availability, PublicEventName
from searcher.contracts.models import ListingImage
from searcher.core.errors import BudgetExceeded
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.ranking.utility import listing_utility
from searcher.receipts.types import LiveCheckReceipt
from searcher.sources.classify import host_of
from searcher.workers.host_io import map_by_host
from searcher.workers.locks import STORE_LOCK

_IMAGE_PREFIXES = (b"\x89PNG", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")


def _looks_like_image(data: bytes) -> bool:
    if data.startswith(_IMAGE_PREFIXES):
        return True
    return len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


class FastOrchestrator(CampaignOrchestrator):
    """Same stages as CampaignOrchestrator. Image GETs overlap across hosts."""

    def _open_engine(self, search_id: str) -> None:
        present = layers_present()
        if not present["discovery"]:
            self.blocked_lanes["discovery"] = "Discovery engine could not be imported."
            return
        try:
            from searcher.workers.bounded_discovery import (
                BoundedDiscoveryEngine,
                install_bounded_discovery,
            )

            install_bounded_discovery()
            self.engine = BoundedDiscoveryEngine(
                self.controller, batch_size=self.batch_size, max_work=self.max_work
            )
        except Exception as exc:
            self.blocked_lanes["discovery"] = f"Discovery engine unavailable: {exc}"
            self.engine = None
        if not present["routing"]:
            self.blocked_lanes["routing"] = (
                "Retrieval, matching, authenticity, or ranking could not be imported."
            )
        del search_id

    def _download_listing_image(
        self,
        image: ListingImage,
        *,
        search_id: str,
        http: Any,
        usage: Any,
    ) -> tuple[ListingImage, bool]:
        if image.content_digest or not image.remote_url:
            return image, False
        if usage.would_exceed(images=1) is not None:
            return image, False
        remote = image.remote_url
        if not remote.startswith(("http://", "https://")):
            return image, False
        try:
            response = http.get(remote, pace=False)
        except Exception:
            return image, False
        body = getattr(response, "body", b"") or b""
        if getattr(response, "status", 0) != 200 or not _looks_like_image(body):
            return image, False
        if usage.would_exceed(images=1, bytes=len(body)) is not None:
            return image, False
        with STORE_LOCK:
            digest = self.controller.store.put_bytes(
                body, zone="incoming", campaign_id=search_id, private=True
            )
        usage.consume(images=1, bytes=len(body))
        return image.model_copy(update={"content_digest": digest}), True

    def _acquire(self, search_id: str) -> None:
        candidates = self.controller.repos.list_candidates(search_id)
        if not candidates or self.engine is None:
            return
        http = getattr(self.engine, "http", None)
        if http is None:
            return
        for per_candidate in (1, None):
            usage = self.controller.usage(search_id)
            listed = self.controller.repos.list_candidates(search_id)
            jobs: list[tuple[str, int, ListingImage]] = []
            for candidate in listed:
                pending = 0
                for offset, image in enumerate(candidate.images):
                    if image.content_digest:
                        continue
                    if per_candidate is not None and pending >= per_candidate:
                        continue
                    jobs.append((candidate.candidate_id, offset, image))
                    pending += 1
            if not jobs:
                continue
            held_http = http
            held_usage = usage

            def fetch(
                job: tuple[str, int, ListingImage],
                *,
                _http: Any = held_http,
                _usage: Any = held_usage,
            ) -> tuple[str, int, ListingImage, bool]:
                _cid, offset, image = job
                fresh, did = self._download_listing_image(
                    image, search_id=search_id, http=_http, usage=_usage
                )
                return _cid, offset, fresh, did

            fetched = map_by_host(
                jobs,
                fetch,
                host_of_item=lambda job: host_of(job[2].remote_url or "") or job[0],
            )
            by_id = {item.candidate_id: item for item in listed}
            changed: dict[str, list[ListingImage]] = {}
            for cid, offset, fresh, did in fetched:
                if not did:
                    continue
                target = by_id.get(cid)
                if target is None:
                    continue
                images = changed.setdefault(cid, list(target.images))
                if 0 <= offset < len(images):
                    images[offset] = fresh
            for cid, images in changed.items():
                target = by_id[cid]
                self.controller.repos.upsert_candidate(
                    search_id, target.model_copy(update={"images": images})
                )
        self.controller.persist_usage(search_id)

    def _broad(self, search_id: str) -> None:
        self._embed_acquired_images(search_id)
        super()._broad(search_id)

    def _embed_acquired_images(self, search_id: str) -> None:
        """Embed every acquired listing image in one batch before scoring."""
        try:
            from searcher.retrieval.embeddings import embed_pngs, resolve_backend
        except Exception:
            return
        backend = resolve_backend()
        if backend is None:
            return
        blobs: list[bytes] = []
        try:
            runtime = self.controller.repos.get_runtime(search_id)
            for digest in runtime.get("reference_digests") or []:
                try:
                    blobs.append(self.controller.store.get(str(digest), campaign_id=search_id))
                except Exception:
                    continue
        except Exception:
            pass
        for candidate in self.controller.repos.list_candidates(search_id):
            for image in candidate.images:
                if not image.content_digest:
                    continue
                try:
                    blobs.append(
                        self.controller.store.get(image.content_digest, campaign_id=search_id)
                    )
                except Exception:
                    continue
        if blobs:
            embed_pngs(blobs, backend)

    def _live(self, search_id: str) -> None:
        candidates = self._candidates_for_match(search_id)
        if not candidates:
            return
        updated = candidates
        if self.engine is not None:
            try:
                live_and_verify = getattr(self.engine, "live_and_verify_all", None)
                if callable(live_and_verify):
                    updated = live_and_verify(search_id, candidates)
                else:
                    updated = self.engine.live_check_all(search_id, candidates)
                    updated = self.engine.verify_all(search_id, updated)
            except BudgetExceeded:
                self.blocked_lanes["live_check"] = "budget exhausted during live check"
                listed = self.controller.repos.list_candidates(search_id)
                by_id = {item.candidate_id: item for item in listed}
                updated = [by_id.get(item.candidate_id, item) for item in candidates]
            except Exception as exc:
                self.blocked_lanes["live_check"] = str(exc)
                updated = candidates
        now = utc_now()
        for candidate in updated:
            live = candidate.availability is Availability.LIVE
            dest = live and candidate.availability is Availability.LIVE
            self._destination_attested[candidate.candidate_id] = _from_index_feed(candidate)
            self._destination_verified[candidate.candidate_id] = dest
            utility = listing_utility(candidate, destination_verified=dest)
            if not any(
                row["kind"] == "LISTING_UTILITY"
                and row.get("candidate_id") == candidate.candidate_id
                for row in self.controller.repos.list_scores(search_id)
            ):
                self.controller.repos.insert_score(
                    search_id,
                    new_id(),
                    "LISTING_UTILITY",
                    utility.utility_score,
                    1.0 if live else 0.0,
                    1.0 if live else 0.0,
                    utility.model_dump(mode="json"),
                    candidate_id=candidate.candidate_id,
                )
            self.controller.emit(
                search_id,
                PublicEventName.CANDIDATE_UPDATED.value,
                payload={"candidate_id": candidate.candidate_id},
                actor="orchestrator",
            )
        self.controller.store_receipt(
            LiveCheckReceipt(
                search_id=search_id,
                result_ids=[item.candidate_id for item in updated],
                refreshed=self.engine is not None and "live_check" not in self.blocked_lanes,
                reason="live check of discovered listings",
            ).seal()
        )
        self.controller.set_runtime(
            search_id,
            destination_verified=self._destination_verified,
            destination_attested=self._destination_attested,
        )
        del now
