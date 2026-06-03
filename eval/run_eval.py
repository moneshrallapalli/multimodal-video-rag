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
from metrics import score_query, summarize_scores  # noqa: E402
from schema import GoldenQuery  # noqa: E402
from shared import settings  # noqa: E402
from shared.bm25 import BM25Encoder  # noqa: E402
from shared.schemas import SearchRequest, SearchResponse  # noqa: E402

DEFAULT_OUTPUT = Path("apps/web/src/data/eval-results.json")

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
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic seed eval")
    parser.add_argument("--golden", default="eval/golden/seed.jsonl")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--retrieval-depth", type=int, default=10)
    args = parser.parse_args()

    rows = load_golden(Path(args.golden))
    artifact = run_eval(rows, retrieval_depth=args.retrieval_depth)
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


def run_eval(rows: list[GoldenQuery], *, retrieval_depth: int) -> dict[str, Any]:
    per_config: dict[str, list[dict[str, Any]]] = {}
    config_summaries: list[dict[str, Any]] = []
    no_answer_by_config: dict[str, dict[str, Any]] = {}
    bm25_encoder = _load_seed_bm25(rows)

    for config in CONFIGS:
        graph_config = _graph_config(config)
        pipeline = QueryPipeline(
            config=graph_config,
            transcript_bm25=bm25_encoder if graph_config.enable_hybrid_transcript else None,
        )
        query_rows = []
        scores = []
        for row in rows:
            response = pipeline.run(
                SearchRequest(query=row.query, video_id=row.video_id, top_k=retrieval_depth)
            )
            score = score_query(row, response)
            scores.append(score)
            query_rows.append(_query_output(row, response, score))

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
                "bm25_loaded": (
                    bm25_encoder is not None if graph_config.enable_hybrid_transcript else None
                ),
            }
        )
        no_answer_by_config[str(config["id"])] = summary["no_answer"]
        per_config[str(config["id"])] = query_rows

    primary_config = "dense"
    return {
        "meta": {
            "status": "real_seed",
            "note": (
                "Real seed evaluation over one indexed video. Metrics are useful for harness "
                "validation, not final portfolio claims."
            ),
            "golden_set_size": len(rows),
            "judge": "not_run",
            "ragas_status": "skipped_seed_eval",
            "retrieval_depth": retrieval_depth,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "primary_config": primary_config,
        },
        "configs": config_summaries,
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
    )


def _load_seed_bm25(rows: list[GoldenQuery]) -> BM25Encoder | None:
    if not settings.s3_bucket:
        return None

    video_ids = {row.video_id for row in rows if row.video_id}
    if len(video_ids) != 1:
        return None

    return BM25Encoder.load_from_s3(bucket=settings.s3_bucket, video_id=next(iter(video_ids)))


def _query_output(
    row: GoldenQuery,
    response: SearchResponse,
    score,
) -> dict[str, Any]:
    return {
        "id": row.id,
        "query": row.query,
        "type": row.type,
        "expected_modality": row.expected_modality,
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
    }


if __name__ == "__main__":
    main()
