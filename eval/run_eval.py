"""Run the seed evaluation and write a dashboard-ready JSON artifact.

Usage:
    uv run python eval/run_eval.py --golden eval/golden/seed.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph import QueryPipeline  # noqa: E402
from graph.models import GraphConfig  # noqa: E402
from judge import AnswerJudge, HaikuAnswerJudge, summarize_judgments  # noqa: E402
from metrics import score_query, summarize_scores  # noqa: E402
from schema import GoldenQuery  # noqa: E402
from shared import settings  # noqa: E402
from shared.bm25 import BM25Encoder  # noqa: E402
from shared.schemas import SearchRequest, SearchResponse  # noqa: E402

DEFAULT_OUTPUT = Path("apps/web/src/data/eval-results.json")
_CORPUS_ENCODER_KEY = "__corpus__"

CONFIGS = [
    {
        "id": "dense",
        "label": "Dense only",
        "min_source_score": 0.2,
    },
    {
        "id": "dense_loose_gate",
        "label": "Dense + loose gate",
        "min_source_score": 0.05,
    },
    {
        "id": "dense_strict_gate",
        "label": "Dense + strict gate",
        "min_source_score": 0.5,
    },
    {
        "id": "hybrid",
        "label": "Hybrid BM25",
        "min_source_score": 0.2,
        "enable_hybrid_transcript": True,
    },
    {
        "id": "hybrid_rerank",
        "label": "Hybrid + rerank",
        "min_source_score": 0.2,
        "enable_hybrid_transcript": True,
        "enable_cross_encoder_rerank": True,
    },
    {
        "id": "hybrid_rewrite",
        "label": "Hybrid + rewrite",
        "min_source_score": 0.2,
        "enable_hybrid_transcript": True,
        "enable_query_rewrite": True,
    },
    {
        "id": "production",
        "label": "Production",
        "min_source_score": 0.2,
        "enable_hybrid_transcript": True,
        "enable_cross_encoder_rerank": True,
        "enable_query_rewrite": True,
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic seed eval")
    parser.add_argument("--golden", default="eval/golden/seed.jsonl")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--retrieval-depth", type=int, default=10)
    parser.add_argument("--judge", choices=["none", "haiku"], default="none")
    parser.add_argument(
        "--judge-configs",
        default="dense,production",
        help="Comma-separated config ids to judge when --judge is enabled.",
    )
    args = parser.parse_args()

    rows = load_golden(Path(args.golden))
    artifact = run_eval(
        rows,
        retrieval_depth=args.retrieval_depth,
        judge_mode=args.judge,
        judge_config_ids=_parse_config_ids(args.judge_configs),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({"output": str(output), "configs": len(artifact["configs"])}, indent=2))


def load_golden(path: Path) -> list[GoldenQuery]:
    return [
        GoldenQuery.model_validate(json.loads(line))
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def run_eval(
    rows: list[GoldenQuery],
    *,
    retrieval_depth: int,
    judge_mode: str = "none",
    judge_config_ids: set[str] | None = None,
    answer_judge: AnswerJudge | None = None,
) -> dict[str, Any]:
    per_config: dict[str, list[dict[str, Any]]] = {}
    config_summaries: list[dict[str, Any]] = []
    no_answer_by_config: dict[str, dict[str, Any]] = {}
    bm25_encoders = _load_bm25_encoders(rows)
    bm25_status = _bm25_status(rows, bm25_encoders)
    judge_config_ids = judge_config_ids or set()
    judge = answer_judge
    if judge_mode == "haiku" and judge is None:
        judge = HaikuAnswerJudge()
    judgments_by_config: dict[str, list[dict[str, Any]]] = {
        config_id: [] for config_id in judge_config_ids
    }
    judgment_rows: dict[str, list[dict[str, Any]]] = {
        config_id: [] for config_id in judge_config_ids
    }

    for config in CONFIGS:
        config_id = str(config["id"])
        effective_config = dict(config)
        if judge is None or config_id not in judge_config_ids:
            effective_config["enable_answer_generation"] = False
        print(f"[eval] running {config_id} ({len(rows)} queries)", file=sys.stderr, flush=True)
        graph_config = _graph_config(effective_config)
        pipeline = QueryPipeline(config=graph_config)
        query_rows = []
        scores = []
        for index, row in enumerate(rows, start=1):
            if index == 1 or index % 10 == 0 or index == len(rows):
                print(
                    f"[eval] {config_id}: query {index}/{len(rows)}",
                    file=sys.stderr,
                    flush=True,
                )
            if graph_config.enable_hybrid_transcript:
                pipeline.transcript_bm25 = _bm25_for_row(row, bm25_encoders)
            response = pipeline.run(
                SearchRequest(query=row.query, video_id=row.video_id, top_k=retrieval_depth)
            )
            score = score_query(row, response)
            judgment = None
            if (
                judge is not None
                and str(config["id"]) in judge_config_ids
                and row.expected_modality != "none"
                and not response.refused
            ):
                judgment = judge.score(row, response)
                judgments_by_config[str(config["id"])].append(judgment)
                judgment_rows[str(config["id"])].append({"id": row.id, **judgment})
            scores.append(score)
            query_rows.append(_query_output(row, response, score, judgment=judgment))

        summary = summarize_scores(scores)
        config_summaries.append(
            {
                "id": config["id"],
                "label": config["label"],
                "recall_at_5": summary["recall_at_5"],
                "recall_at_10": summary["recall_at_10"],
                "mrr": summary["mrr"],
                "timestamp_at_5s": summary["timestamp_at_5s"],
                "timestamp_at_10s": summary["timestamp_at_10s"],
                "modality_acc": summary["modality_acc"],
                "no_answer_f1": summary["no_answer"]["f1"],
                "min_source_score": config["min_source_score"],
                "enable_hybrid_transcript": graph_config.enable_hybrid_transcript,
                "enable_cross_encoder_rerank": graph_config.enable_cross_encoder_rerank,
                "enable_query_rewrite": graph_config.enable_query_rewrite,
                "enable_answer_generation": graph_config.enable_answer_generation,
                "bm25_loaded": (
                    bm25_status["loaded_all"] if graph_config.enable_hybrid_transcript else None
                ),
                "bm25_corpus_loaded": (
                    bm25_status["loaded_corpus"] if graph_config.enable_hybrid_transcript else None
                ),
                "bm25_loaded_video_ids": (
                    bm25_status["loaded_video_ids"] if graph_config.enable_hybrid_transcript else []
                ),
                "bm25_missing_video_ids": (
                    bm25_status["missing_video_ids"]
                    if graph_config.enable_hybrid_transcript
                    else []
                ),
            }
        )
        no_answer_by_config[str(config["id"])] = summary["no_answer"]
        per_config[str(config["id"])] = query_rows

    primary_config = "production"
    video_count = len(_golden_expected_video_ids(rows))
    status = "real_expanded" if video_count > 1 or len(rows) > 15 else "real_seed"
    return {
        "meta": {
            "status": status,
            "note": (
                f"Real evaluation over {video_count} indexed video"
                f"{'' if video_count == 1 else 's'} and {len(rows)} hand-labeled queries. "
                "Metrics are regression signals, not universal benchmark claims."
            ),
            "golden_set_size": len(rows),
            "indexed_video_count": video_count,
            "judge": judge_mode if judge_mode != "none" else "not_run",
            "ragas_status": "not_run",
            "retrieval_depth": retrieval_depth,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "primary_config": primary_config,
        },
        "configs": config_summaries,
        "judge": _judge_output(
            mode=judge_mode,
            judgments_by_config=judgments_by_config,
            judgment_rows=judgment_rows,
        ),
        "ragas": {},
        "no_answer": no_answer_by_config[primary_config],
        "no_answer_by_config": no_answer_by_config,
        "per_query": per_config,
    }


def _graph_config(config: dict[str, Any]) -> GraphConfig:
    threshold = float(config["min_source_score"])
    return GraphConfig(
        retrieve_top_k=20,
        min_source_score=threshold,
        min_transcript_source_score=float(config.get("min_transcript_source_score", threshold)),
        min_visual_source_score=float(config.get("min_visual_source_score", threshold)),
        enable_hybrid_transcript=bool(config.get("enable_hybrid_transcript", False)),
        enable_cross_encoder_rerank=bool(config.get("enable_cross_encoder_rerank", False)),
        enable_query_rewrite=bool(config.get("enable_query_rewrite", False)),
        enable_answer_generation=bool(config.get("enable_answer_generation", True)),
    )


def _parse_config_ids(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _load_bm25_encoders(rows: list[GoldenQuery]) -> dict[str, BM25Encoder]:
    if not settings.s3_bucket:
        return {}

    encoders: dict[str, BM25Encoder] = {}
    corpus_encoder = BM25Encoder.load_corpus_from_s3(bucket=settings.s3_bucket)
    if corpus_encoder is not None:
        encoders[_CORPUS_ENCODER_KEY] = corpus_encoder
    for video_id in _golden_video_ids(rows):
        encoder = BM25Encoder.load_from_s3(bucket=settings.s3_bucket, video_id=video_id)
        if encoder is not None:
            encoders[video_id] = encoder
    return encoders


def _bm25_for_row(
    row: GoldenQuery,
    encoders: dict[str, BM25Encoder],
) -> BM25Encoder | None:
    if not row.video_id:
        return encoders.get(_CORPUS_ENCODER_KEY)
    return encoders.get(row.video_id)


def _bm25_status(
    rows: list[GoldenQuery],
    encoders: dict[str, BM25Encoder],
) -> dict[str, Any]:
    video_ids = _golden_video_ids(rows)
    loaded_ids = [video_id for video_id in video_ids if video_id in encoders]
    missing_ids = [video_id for video_id in video_ids if video_id not in encoders]
    return {
        "loaded_all": bool(video_ids) and not missing_ids,
        "loaded_corpus": _CORPUS_ENCODER_KEY in encoders,
        "loaded_video_ids": loaded_ids,
        "missing_video_ids": missing_ids,
    }


def _golden_video_ids(rows: list[GoldenQuery]) -> list[str]:
    return sorted({row.video_id for row in rows if row.video_id})


def _golden_expected_video_ids(rows: list[GoldenQuery]) -> list[str]:
    return sorted(
        {
            row.expected_video_id or row.video_id
            for row in rows
            if row.expected_video_id or row.video_id
        }
    )


def _query_output(
    row: GoldenQuery,
    response: SearchResponse,
    score,
    *,
    judgment: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "id": row.id,
        "query": row.query,
        "type": row.type,
        "expected_modality": row.expected_modality,
        "expected_video_id": row.expected_video_id,
        "relevant_timestamps": row.relevant_timestamps,
        "response": {
            "intent": response.intent,
            "rewritten_query": response.rewritten_query,
            "refused": response.refused,
            "confidence": response.confidence,
            "answer": response.answer,
            "results": [
                {
                    "rank": result.rank,
                    "video_id": result.video_id,
                    "modality": result.modality,
                    "start_seconds": result.start_seconds,
                    "end_seconds": result.end_seconds,
                    "score": result.score,
                    "snippet": result.snippet,
                }
                for result in response.results
            ],
        },
        "metrics": {
            "recall_at_5": score.recall_at_5,
            "recall_at_10": score.recall_at_10,
            "mrr": score.mrr,
            "timestamp_at_5s": score.timestamp_at_5s,
            "timestamp_at_10s": score.timestamp_at_10s,
            "modality_correct": score.modality_correct,
            "expected_no_answer": score.expected_no_answer,
            "predicted_refused": score.predicted_refused,
        },
        "judge": judgment,
    }


def _judge_output(
    *,
    mode: str,
    judgments_by_config: dict[str, list[dict[str, Any]]],
    judgment_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if mode == "none":
        return {"mode": "none", "configs": [], "per_query": {}}
    return {
        "mode": mode,
        "configs": [
            {"id": config_id, **summarize_judgments(judgments)}
            for config_id, judgments in judgments_by_config.items()
        ],
        "per_query": judgment_rows,
    }


if __name__ == "__main__":
    main()
