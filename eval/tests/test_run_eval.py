"""Eval runner output-shape tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("eval").resolve()))

from run_eval import load_golden  # noqa: E402


def test_load_golden_reads_seed_rows():
    rows = load_golden(Path("eval/golden/seed.jsonl"))

    assert rows[0].id == "q001"
    assert rows[-1].expected_modality == "none"
