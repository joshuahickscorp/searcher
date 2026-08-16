"""Multipart intake. Validation is the existing hardened path only."""

from __future__ import annotations

from dataclasses import dataclass

from starlette.datastructures import FormData, UploadFile

from searcher.api.dependencies import ApiError
from searcher.core.config import Settings
from searcher.core.errors import InputError, MalformedContentError
from searcher.reference.validation import refuse_path_name, validate_upload_bytes

_IMAGE_KEYS = frozenset({"images", "images[]", "image"})
_TAG_KEYS = frozenset({"tags", "tags[]"})


@dataclass(frozen=True, slots=True)
class ParsedCreate:
    uploads: list[tuple[bytes, str | None]]
    text: str | None
    tags: list[str]
    client_search_id: str | None


def _field_values(form: FormData, names: frozenset[str]) -> list[str]:
    values: list[str] = []
    for key, value in form.multi_items():
        if key not in names:
            continue
        if isinstance(value, UploadFile):
            continue
        text = str(value).strip()
        if text:
            values.append(text)
    return values


async def parse_create_form(form: FormData, settings: Settings) -> ParsedCreate:
    uploads: list[tuple[bytes, str | None]] = []
    total = 0
    for key, value in form.multi_items():
        if key not in _IMAGE_KEYS or not isinstance(value, UploadFile):
            continue
        declared = value.filename or None
        if declared:
            try:
                refuse_path_name(declared)
            except InputError as exc:
                raise ApiError(422, "validation", _public_input_message(exc)) from exc
        data = await value.read()
        total += len(data)
        if total > settings.max_total_upload_bytes:
            raise ApiError(
                422,
                "validation",
                "Combined upload size exceeds the configured total cap.",
            )
        try:
            validate_upload_bytes(data, declared_name=declared, settings=settings)
        except InputError as exc:
            raise ApiError(422, "validation", _public_input_message(exc)) from exc
        except MalformedContentError as exc:
            raise ApiError(422, "malformed_content", _public_input_message(exc)) from exc
        uploads.append((data, declared))

    if len(uploads) < 1:
        raise ApiError(
            422,
            "validation",
            "A search needs at least one image. The server is the validator.",
        )
    if len(uploads) > settings.max_images_per_search:
        raise ApiError(
            422,
            "validation",
            f"A search can include at most {settings.max_images_per_search} images. "
            "The server is the validator.",
        )

    text_values = _field_values(form, frozenset({"text"}))
    tags = _field_values(form, _TAG_KEYS)
    client_values = _field_values(form, frozenset({"client_search_id"}))
    text = text_values[0] if text_values else None
    client_search_id = client_values[0] if client_values else None
    return ParsedCreate(
        uploads=uploads,
        text=text,
        tags=tags,
        client_search_id=client_search_id,
    )


def _public_input_message(exc: Exception) -> str:
    raw = str(exc)
    if raw.startswith("["):
        closing = raw.find("]")
        if closing != -1:
            raw = raw[closing + 1 :].strip()
    if "search_id=" in raw:
        raw = raw.split("search_id=", 1)[0].rstrip(" (").strip()
    return raw or "The upload was rejected."
