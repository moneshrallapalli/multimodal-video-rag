"""Eval runner output-shape tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("eval").resolve()))

import run_eval as eval_runner  # noqa: E402
from run_eval import _graph_config, load_golden  # noqa: E402
from schema import GoldenQuery  # noqa: E402


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
            "enable_answer_generation": False,
        }
    )

    assert config.min_source_score == 0.5
    assert config.min_transcript_source_score == 0.5
    assert config.min_visual_source_score == 0.5
    assert config.enable_hybrid_transcript is True
    assert config.enable_cross_encoder_rerank is True
    assert config.enable_query_rewrite is True
    assert config.enable_answer_generation is False


def test_load_bm25_encoders_loads_each_golden_video_once(monkeypatch):
    rows = [
        _golden("q1", "vid-b"),
        _golden("q2", "vid-a"),
        _golden("q3", "vid-b"),
        _golden("q4", None),
    ]
    calls: list[tuple[str, str]] = []

    def fake_load_from_s3(*, bucket: str, video_id: str):
        calls.append((bucket, video_id))
        return f"encoder:{video_id}"

    monkeypatch.setattr(eval_runner.settings, "s3_bucket", "bucket")
    monkeypatch.setattr(eval_runner.BM25Encoder, "load_from_s3", staticmethod(fake_load_from_s3))
    monkeypatch.setattr(
        eval_runner.BM25Encoder,
        "load_corpus_from_s3",
        staticmethod(lambda *, bucket: "encoder:corpus"),
    )

    encoders = eval_runner._load_bm25_encoders(rows)

    assert calls == [("bucket", "vid-a"), ("bucket", "vid-b")]
    assert encoders == {
        "__corpus__": "encoder:corpus",
        "vid-a": "encoder:vid-a",
        "vid-b": "encoder:vid-b",
    }


def test_bm25_status_reports_partial_multi_video_coverage():
    rows = [_golden("q1", "vid-a"), _golden("q2", "vid-b"), _golden("q3", None)]

    status = eval_runner._bm25_status(rows, {"vid-b": object()})

    assert status == {
        "loaded_all": False,
        "loaded_corpus": False,
        "loaded_video_ids": ["vid-b"],
        "missing_video_ids": ["vid-a"],
    }


def test_bm25_for_row_uses_matching_video_encoder():
    rows = [_golden("q1", "vid-a"), _golden("q2", None)]
    encoders = {"vid-a": object(), "vid-b": object()}

    assert eval_runner._bm25_for_row(rows[0], encoders) is encoders["vid-a"]
    assert eval_runner._bm25_for_row(rows[1], encoders) is None


def test_bm25_for_row_uses_corpus_encoder_for_unfiltered_query():
    row = _golden("q1", None)
    encoders = {"__corpus__": object()}

    assert eval_runner._bm25_for_row(row, encoders) is encoders["__corpus__"]


def _golden(query_id: str, video_id: str | None) -> GoldenQuery:
    return GoldenQuery(
        id=query_id,
        query="where is the relevant moment?",
        type="transcript",
        video_id=video_id,
        relevant_timestamps=[(1.0, 2.0)],
        expected_modality="transcript",
    )
