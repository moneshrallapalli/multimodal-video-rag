"""Evaluation dataset schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvalType = Literal["visual", "transcript", "hybrid", "timestamp", "summary", "no_answer"]
ExpectedModality = Literal["visual", "transcript", "hybrid", "none"]


class GoldenQuery(BaseModel):
    id: str
    query: str
    type: EvalType
    video_id: str | None = None
    relevant_timestamps: list[tuple[float, float]] = Field(default_factory=list)
    expected_modality: ExpectedModality
    reference_answer: str | None = None
    notes: str = ""
