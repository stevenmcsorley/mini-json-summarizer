"""HTTP route handlers for the summarization API."""

from __future__ import annotations

import time
from json import JSONDecodeError
from typing import Any, Dict, Iterable, List, Type

import anyio
import httpx
import orjson
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.summarizer.json_path import path_exists
from app.summarizer.models import SummarizationRequest
from app.summarizer.service import summarize

from .schemas import (
    ChatRequestModel,
    ChatResponseModel,
    ChatMessageModel,
    SummarizeRequestModel,
    SummaryBulletModel,
    SummaryResponseModel,
)


router = APIRouter()


async def _load_request_model(
    http_request: Request, model_cls: Type[BaseModel], settings: Settings
) -> BaseModel:
    header_length = http_request.headers.get("content-length")
    if header_length:
        try:
            content_length = int(header_length)
        except ValueError:
            content_length = None
        else:
            if (
                content_length is not None
                and content_length > settings.max_payload_bytes
            ):
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail={
                        "error": "payload_too_large",
                        "limit_bytes": settings.max_payload_bytes,
                    },
                )

    body_bytes = await http_request.body()
    if body_bytes and len(body_bytes) > settings.max_payload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "payload_too_large",
                "limit_bytes": settings.max_payload_bytes,
            },
        )

    if not body_bytes:
        data: Dict[str, Any] = {}
    else:
        try:
            data = orjson.loads(body_bytes)
        except orjson.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_json", "details": str(exc)},
            ) from exc

    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


async def load_summary_request(http_request: Request) -> SummarizeRequestModel:
    settings = get_settings()
    return await _load_request_model(http_request, SummarizeRequestModel, settings)


async def load_chat_request(http_request: Request) -> ChatRequestModel:
    settings = get_settings()
    return await _load_request_model(http_request, ChatRequestModel, settings)


async def _fetch_json(url: str, settings: Settings) -> Any:
    timeout = httpx.Timeout(10.0, read=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type and not url.lower().endswith(".json"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_json_source",
                    "details": "URL did not return JSON content.",
                },
            )
        try:
            return response.json()
        except JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_json", "details": str(exc)},
            ) from exc


def _enforce_depth_limit(payload: Any, max_depth: int) -> None:
    stack: List[tuple[Any, int]] = [(payload, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > max_depth:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "depth_limit", "limit": max_depth},
            )
        if isinstance(node, dict):
            for child in node.values():
                stack.append((child, depth + 1))
        elif isinstance(node, list):
            for child in node:
                stack.append((child, depth + 1))


def _validate_payload(payload: Any, settings: Settings) -> int:
    try:
        payload_bytes = orjson.dumps(payload)
    except orjson.JSONEncodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_json",
                "details": f"Payload is not JSON serializable: {exc}",
            },
        ) from exc

    if len(payload_bytes) > settings.max_payload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "payload_too_large",
                "limit_bytes": settings.max_payload_bytes,
            },
        )

    _enforce_depth_limit(payload, settings.max_json_depth)
    return len(payload_bytes)


def _apply_focus_override(messages: Iterable[ChatMessageModel]) -> List[str]:
    for message in reversed(list(messages)):
        if message.role == "user":
            tokens = [
                token.strip() for token in message.content.split() if token.strip()
            ]
            return tokens
    return []


def _settings_for_request(settings: Settings, disable_redaction: bool) -> Settings:
    if not disable_redaction:
        return settings
    return settings.model_copy(update={"pii_redaction_enabled": False})


def _build_evidence_stats(
    bundle, bytes_examined: int, elapsed_ms: int
) -> Dict[str, int]:
    """Summarise metadata about the evidence bundle for traceability."""
    payload_ref = (
        bundle.metadata.get("payload") if isinstance(bundle.metadata, dict) else None
    )
    baseline_ref = None
    if isinstance(bundle.metadata, dict):
        baseline_ref = bundle.metadata.get("baseline")

    def _path_present(path: str) -> bool:
        if payload_ref is not None and path_exists(payload_ref, path):
            return True
        if baseline_ref is not None and path_exists(baseline_ref, path):
            return True
        return False

    unique_paths = {
        citation.path
        for bullet in bundle.bullets
        for citation in bullet.citations
        if _path_present(citation.path)
    }
    return {
        "paths_count": len(unique_paths),
        "bytes_examined": bytes_examined,
        "elapsed_ms": elapsed_ms,
    }


@router.post("/v1/summarize-json")
async def summarize_json(
    summary_request: SummarizeRequestModel = Depends(load_summary_request),
):
    try:
        settings = get_settings()
        payload_source = summary_request.payload
        if payload_source is None and summary_request.payload_url:
            payload_source = await _fetch_json(
                str(summary_request.payload_url), settings
            )

        baseline_payload = summary_request.baseline_json
        if baseline_payload is None and summary_request.baseline_url:
            baseline_payload = await _fetch_json(
                str(summary_request.baseline_url), settings
            )

        if payload_source is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_request",
                    "details": "`json` or `json_url` is required.",
                },
            )

        active_settings = _settings_for_request(
            settings, summary_request.disable_redaction
        )
        payload_bytes = _validate_payload(payload_source, active_settings)
        baseline_bytes = 0
        if baseline_payload is not None:
            baseline_bytes = _validate_payload(baseline_payload, active_settings)

        summarization_request = SummarizationRequest(
            payload=payload_source,
            focus=summary_request.focus,
            engine=summary_request.engine,
            length=summary_request.length,
            style=summary_request.style,
            template=summary_request.template,
            baseline_payload=baseline_payload,
            include_root_summary=summary_request.include_root_summary,
        )

        start_time = time.perf_counter()
        evidence_bundle = summarize(summarization_request, settings=active_settings)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        evidence_stats = _build_evidence_stats(
            evidence_bundle,
            bytes_examined=payload_bytes + baseline_bytes,
            elapsed_ms=elapsed_ms,
        )

        if summary_request.stream:

            async def event_stream():
                for bullet in evidence_bundle.bullets:
                    bullet_payload = {
                        "phase": "summary",
                        "bullet": SummaryBulletModel.from_domain(bullet).model_dump(),
                    }
                    yield f"data: {orjson.dumps(bullet_payload).decode()}\n\n"
                    await anyio.sleep(active_settings.streaming_chunk_delay_ms / 1000)
                footer = {"phase": "complete", "evidence_stats": evidence_stats}
                yield f"data: {orjson.dumps(footer).decode()}\n\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        response_payload = SummaryResponseModel(
            engine=evidence_bundle.engine,
            focus=evidence_bundle.focus,
            redactions_applied=evidence_bundle.redactions_applied,
            bullets=[
                SummaryBulletModel.from_domain(bullet)
                for bullet in evidence_bundle.bullets
            ],
            evidence_stats=evidence_stats,
        )
        return JSONResponse(content=response_payload.model_dump())
    except HTTPException as exc:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        raise


@router.post("/v1/chat", response_model=ChatResponseModel)
async def chat(
    chat_request: ChatRequestModel = Depends(load_chat_request),
):
    try:
        settings = get_settings()
        payload = chat_request.payload
        if payload is None and chat_request.payload_url:
            payload = await _fetch_json(str(chat_request.payload_url), settings)

        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_request",
                    "details": "`json` or `json_url` is required for chat.",
                },
            )

        focus_hints = _apply_focus_override(chat_request.messages)
        combined_focus = list(dict.fromkeys(chat_request.focus + focus_hints))

        payload_bytes = _validate_payload(payload, settings)
        summarization_request = SummarizationRequest(
            payload=payload,
            focus=combined_focus,
            engine=chat_request.engine,
            length=chat_request.length,
            style=chat_request.style,
            template=chat_request.template,
            include_root_summary=chat_request.include_root_summary,
        )
        start_time = time.perf_counter()
        bundle = summarize(summarization_request, settings=settings)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        evidence_stats = _build_evidence_stats(
            bundle,
            bytes_examined=payload_bytes,
            elapsed_ms=elapsed_ms,
        )
        bullet_models = [
            SummaryBulletModel.from_domain(bullet) for bullet in bundle.bullets
        ]
        reply_lines = [f"- {bullet.text}" for bullet in bundle.bullets]
        reply = "\n".join(reply_lines)

        return ChatResponseModel(
            reply=reply,
            engine=bundle.engine,
            bullets=bullet_models,
            evidence_stats=evidence_stats,
        )
    except HTTPException as exc:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        raise
