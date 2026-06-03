"""Golden seed dataset validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("eval").resolve()))

from schema import GoldenQuery  # noqa: E402


def test_seed_golden_dataset_is_valid():
    _assert_golden_valid(Path("eval/golden/seed.jsonl"), min_rows=12)


def test_expanded_golden_dataset_is_valid():
    rows = _assert_golden_valid(Path("eval/golden/expanded.jsonl"), min_rows=60)

    expected_videos = {
        row.expected_video_id or row.video_id for row in rows if row.expected_modality != "none"
    }
    assert len(expected_videos) >= 3
    assert any(row.video_id is None and row.expected_video_id for row in rows)


def _assert_golden_valid(path: Path, *, min_rows: int) -> list[GoldenQuery]:
    rows = [
        GoldenQuery.model_validate(json.loads(line))
        for line in path.read_text().splitlines()
        if line.strip()
    ]

    assert len(rows) >= min_rows
    assert len({row.id for row in rows}) == len(rows)
    assert any(row.type == "visual" for row in rows)
    assert any(row.type == "transcript" for row in rows)
    assert any(row.type == "hybrid" for row in rows)
    assert any(row.type == "no_answer" for row in rows)
    for row in rows:
        if row.expected_modality == "none":
            assert row.relevant_timestamps == []
            assert row.reference_answer is None
        else:
            assert row.video_id or row.expected_video_id
            assert row.relevant_timestamps
            assert row.reference_answer
    return rows
