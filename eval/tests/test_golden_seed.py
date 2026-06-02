"""Golden seed dataset validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("eval").resolve()))

from schema import GoldenQuery  # noqa: E402


def test_seed_golden_dataset_is_valid():
    path = Path("eval/golden/seed.jsonl")
    rows = [
        GoldenQuery.model_validate(json.loads(line))
        for line in path.read_text().splitlines()
        if line.strip()
    ]

    assert len(rows) >= 12
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
            assert row.relevant_timestamps
            assert row.reference_answer
