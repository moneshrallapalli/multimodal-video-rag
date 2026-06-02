"""Run a direct Pinecone smoke query.

Usage:
    uv run python scripts/query_vectors.py transcript "self sabotage"
    uv run python scripts/query_vectors.py visual "speaker at a desk"
"""

from __future__ import annotations

import argparse

from shared import settings
from shared.embedding import BedrockEmbedder
from shared.pinecone_client import PineconeIndexClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Query a Phase 3 Pinecone index")
    parser.add_argument("modality", choices=["transcript", "visual"])
    parser.add_argument("query")
    parser.add_argument("--video-id", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    embedder = BedrockEmbedder()
    if args.modality == "transcript":
        index_name = settings.pinecone_transcript_index
        vector = embedder.embed_text(args.query)
    else:
        index_name = settings.pinecone_visual_index
        vector = embedder.embed_visual_query(args.query)

    metadata_filter = {"video_id": {"$eq": args.video_id}} if args.video_id else None
    hits = PineconeIndexClient.from_index_name(index_name).query(
        vector,
        top_k=args.top_k,
        metadata_filter=metadata_filter,
    )
    for hit in hits:
        print(hit.model_dump_json())


if __name__ == "__main__":
    main()
