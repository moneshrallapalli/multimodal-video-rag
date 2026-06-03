"""Eval runner output-shape tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("eval").resolve()))

from run_eval import _graph_config, load_golden  # noqa: E402


def test_load_golden_reads_seed_rows():
    rows = load_golden(Path("eval/golden/seed.jsonl"))

    assert rows[0].id == "q001"
    assert rows[-1].expected_modality == "none"


def test_graph_config_maps_eval_threshold_and_ablation_toggles():
    config = _graph_config(
        {
            "min_source_score": 0.5,
            "enable_hybrid_transcript": True,
            "enable_cross_encoder_rerank": True,
            "enable_query_rewrite": True,
        }
    )

    assert config.min_source_score == 0.5
    assert config.min_transcript_source_score == 0.5
    assert config.min_visual_source_score == 0.5
    assert config.enable_hybrid_transcript is True
    assert config.enable_cross_encoder_rerank is True
    assert config.enable_query_rewrite is True
