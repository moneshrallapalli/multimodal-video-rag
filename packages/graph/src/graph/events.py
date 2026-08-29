"""Helpers for live QueryPipeline node events. No retrieval math lives here."""

from __future__ import annotations

from typing import Any

from shared.schemas import PipelineHitSnippet


def hit_snippets(hits: list[dict[str, Any]], *, limit: int = 4) -> list[dict[str, Any]]:
    """Trim retrieval hits to the fields the live pane is allowed to show."""
    snippets: list[dict[str, Any]] = []
    for hit in hits[:limit]:
        text = str(hit.get("snippet") or "")
        snippets.append(
            PipelineHitSnippet(
                video_id=str(hit.get("video_id") or ""),
                start_seconds=float(hit.get("start_seconds") or 0.0),
                snippet=text[:240],
                score=float(hit["score"]) if hit.get("score") is not None else None,
                modality=str(hit["modality"]) if hit.get("modality") else None,
            ).model_dump()
        )
    return snippets


def retrieve_payload(hits: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(hit["score"]) for hit in hits if hit.get("score") is not None]
    return {
        "hit_count": len(hits),
        "top_score": max(scores) if scores else 0.0,
        "hits": hit_snippets(hits),
    }


def preview_text(text: str | None, *, limit: int = 180) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"
