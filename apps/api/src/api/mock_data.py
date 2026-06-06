"""Deterministic fallback data and public seed catalog."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from itertools import count
from threading import Lock

from shared.ingestion import normalize_youtube_url
from shared.schemas import (
    DemoVideo,
    IngestResponse,
    Job,
    JobsResponse,
    QueryIntent,
    SearchRequest,
    SearchResponse,
    SearchResult,
    VideoArtifactStats,
)

# Standard refusal copy (blueprint §12). Never guess when evidence is weak.
NO_ANSWER_MESSAGE = (
    "I could not find strong evidence for that in the indexed videos. "
    "Try a more specific description, or search within a single video."
)


def _thumb(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _watch(video_id: str) -> str:
    return f"https://youtu.be/{video_id}"


def _stats(segments: int, chunks: int, frames: int) -> VideoArtifactStats:
    return VideoArtifactStats(
        transcript_segments=segments,
        transcript_chunks=chunks,
        visual_frames=frames,
        indexed_vectors=chunks + frames,
        frame_interval_seconds=10,
    )


# ── Public demo library (indexed corpus) ──────────────────────────────

DEMO_VIDEOS: list[DemoVideo] = [
    DemoVideo(
        id="QkdBXUikRQc",
        title="Stop Dreaming and Start Doing | Self-Sabotage",
        author="Olga Loiek",
        domain="Self-improvement",
        thumbnail_url=_thumb("QkdBXUikRQc"),
        youtube_url=_watch("QkdBXUikRQc"),
        duration_seconds=720,
        indexed=True,
        artifact_stats=_stats(98, 15, 13),
    ),
    DemoVideo(
        id="DVtcZQ2QdBg",
        title="10 Ways to Build an Unfair Advantage in Your 20s",
        author="Mia McGrath",
        domain="Career / Finance",
        thumbnail_url=_thumb("DVtcZQ2QdBg"),
        youtube_url=_watch("DVtcZQ2QdBg"),
        duration_seconds=1521,
        indexed=True,
        artifact_stats=_stats(925, 63, 20),
    ),
    DemoVideo(
        id="as9IYFrTiKc",
        title="A Real Sprint Review Meeting Example",
        author="DataMiner by Skyline Communications",
        domain="Product / Agile",
        thumbnail_url=_thumb("as9IYFrTiKc"),
        youtube_url=_watch("as9IYFrTiKc"),
        duration_seconds=404,
        indexed=True,
        artifact_stats=_stats(92, 17, 13),
    ),
    DemoVideo(
        id="u4ZoJKF_VuA",
        title="Start with Why: How Great Leaders Inspire Action",
        author="Simon Sinek",
        domain="TED / Leadership",
        thumbnail_url=_thumb("u4ZoJKF_VuA"),
        youtube_url=_watch("u4ZoJKF_VuA"),
        duration_seconds=1083,
        indexed=True,
        artifact_stats=_stats(345, 45, 20),
    ),
    DemoVideo(
        id="1Gdl-A1DvpA",
        title="Gordon Ramsay Challenges Amateur Cook to Keep Up with Him",
        author="Bon Appetit",
        domain="Cooking",
        thumbnail_url=_thumb("1Gdl-A1DvpA"),
        youtube_url=_watch("1Gdl-A1DvpA"),
        duration_seconds=544,
        indexed=True,
        artifact_stats=_stats(320, 23, 18),
    ),
    DemoVideo(
        id="iCvmsMzlF7o",
        title="The Power of Vulnerability",
        author="Brene Brown",
        domain="Psychology",
        thumbnail_url=_thumb("iCvmsMzlF7o"),
        youtube_url=_watch("iCvmsMzlF7o"),
        duration_seconds=1249,
        indexed=True,
        artifact_stats=_stats(305, 53, 20),
    ),
    DemoVideo(
        id="TGdLss5Srnk",
        title="Sam Altman on Elon Musk suing OpenAI",
        author="Lex Fridman",
        domain="Podcast",
        thumbnail_url=_thumb("TGdLss5Srnk"),
        youtube_url=_watch("TGdLss5Srnk"),
        duration_seconds=595,
        indexed=True,
        artifact_stats=_stats(147, 24, 20),
    ),
    DemoVideo(
        id="E76CUtSHMrU",
        title="Smartphone Awards 2024!",
        author="Marques Brownlee",
        domain="Tech Review",
        thumbnail_url=_thumb("E76CUtSHMrU"),
        youtube_url=_watch("E76CUtSHMrU"),
        duration_seconds=1645,
        indexed=True,
        artifact_stats=_stats(345, 69, 20),
    ),
    DemoVideo(
        id="h6fcK_fRYaI",
        title="The Egg - A Short Story",
        author="Kurzgesagt - In a Nutshell",
        domain="Science Animation",
        thumbnail_url=_thumb("h6fcK_fRYaI"),
        youtube_url=_watch("h6fcK_fRYaI"),
        duration_seconds=444,
        indexed=True,
        artifact_stats=_stats(121, 18, 16),
    ),
    DemoVideo(
        id="v7AYKMP6rOE",
        title="Yoga For Complete Beginners - 20 Minute Home Yoga Workout",
        author="Yoga With Adriene",
        domain="Fitness",
        thumbnail_url=_thumb("v7AYKMP6rOE"),
        youtube_url=_watch("v7AYKMP6rOE"),
        duration_seconds=1415,
        indexed=True,
        artifact_stats=_stats(240, 57, 20),
    ),
    DemoVideo(
        id="Th8JoIan4dg",
        title="How to Get and Evaluate Startup Ideas",
        author="Y Combinator",
        domain="Business / Startup",
        thumbnail_url=_thumb("Th8JoIan4dg"),
        youtube_url=_watch("Th8JoIan4dg"),
        duration_seconds=1930,
        indexed=True,
        artifact_stats=_stats(544, 80, 20),
    ),
    DemoVideo(
        id="arj7oStGLkU",
        title="Inside the Mind of a Master Procrastinator",
        author="Tim Urban",
        domain="Comedy / TED",
        thumbnail_url=_thumb("arj7oStGLkU"),
        youtube_url=_watch("arj7oStGLkU"),
        duration_seconds=836,
        indexed=True,
        artifact_stats=_stats(201, 35, 20),
    ),
    DemoVideo(
        id="uxPdPpi5W4o",
        title="Why Are 96,000,000 Black Balls on This Reservoir?",
        author="Veritasium",
        domain="Science / News",
        thumbnail_url=_thumb("uxPdPpi5W4o"),
        youtube_url=_watch("uxPdPpi5W4o"),
        duration_seconds=705,
        indexed=True,
        artifact_stats=_stats(282, 30, 20),
    ),
]

_VIDEO_TITLES = {v.id: v.title for v in DEMO_VIDEOS}


# ── Indexed "moments": (video_id, start, end, modality, snippet) ───────

_Moment = tuple[str, float, float, str, str]

_MOMENTS: list[_Moment] = [
    # Stop Dreaming and Start Doing — self-sabotage
    (
        "QkdBXUikRQc",
        42,
        70,
        "transcript",
        "The biggest form of self-sabotage is waiting until you feel ready before you start.",
    ),
    (
        "QkdBXUikRQc",
        128,
        155,
        "transcript",
        "Break the goal into the smallest possible first action you can take today.",
    ),
    (
        "QkdBXUikRQc",
        305,
        320,
        "visual",
        "Speaker at a desk with bold on-screen text reading 'STOP DREAMING START DOING'.",
    ),
    (
        "QkdBXUikRQc",
        540,
        566,
        "transcript",
        "Discipline beats motivation, because motivation is unreliable and fades quickly.",
    ),
    # 10 Ways to Build an Unfair Advantage in Your 20s
    (
        "DVtcZQ2QdBg",
        75,
        102,
        "transcript",
        "Compounding skills early in your twenties creates an unfair advantage later on.",
    ),
    (
        "DVtcZQ2QdBg",
        210,
        240,
        "transcript",
        "Build a personal brand by sharing what you learn publicly and consistently.",
    ),
    (
        "DVtcZQ2QdBg",
        360,
        378,
        "visual",
        "Slide listing the ten unfair advantages with bold numbered headings.",
    ),
    (
        "DVtcZQ2QdBg",
        620,
        650,
        "transcript",
        "Networking is about giving value first, before you ask anyone for anything.",
    ),
    (
        "DVtcZQ2QdBg",
        900,
        930,
        "transcript",
        "Learn to negotiate your salary; most people leave money on the table by not asking.",
    ),
    # A Real Sprint Review Meeting Example
    (
        "as9IYFrTiKc",
        30,
        58,
        "transcript",
        "Welcome to the sprint review, where the team demos completed work to stakeholders.",
    ),
    (
        "as9IYFrTiKc",
        180,
        196,
        "visual",
        "Screen share of the product backlog board during the live demo.",
    ),
    (
        "as9IYFrTiKc",
        420,
        448,
        "transcript",
        "The product owner accepts the story once the acceptance criteria are met.",
    ),
    (
        "as9IYFrTiKc",
        700,
        726,
        "transcript",
        "Feedback and action items are captured to feed the next sprint planning.",
    ),
]

# Off-domain triggers that should always refuse (so the no-answer state is demoable).
_OFF_DOMAIN = {
    "weather",
    "recipe",
    "stock",
    "stocks",
    "football",
    "lunch",
    "pizza",
    "bitcoin",
    "horoscope",
    "lottery",
}

_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "is",
    "are",
    "do",
    "does",
    "what",
    "how",
    "where",
    "when",
    "show",
    "me",
    "find",
    "for",
    "and",
    "or",
    "about",
    "at",
    "part",
    "moment",
    "video",
    "talk",
    "speaker",
    "they",
    "he",
    "she",
}

_INTENT_KEYWORDS: dict[QueryIntent, tuple[str, ...]] = {
    "visual": (
        "show",
        "see",
        "slide",
        "whiteboard",
        "diagram",
        "screen",
        "scene",
        "frame",
        "visual",
        "board",
        "picture",
        "look",
        "display",
    ),
    "summary": (
        "summary",
        "summarize",
        "summarise",
        "takeaway",
        "takeaways",
        "main",
        "lessons",
        "overview",
        "recap",
        "points",
    ),
    "timestamp": ("when", "timestamp", "what point", "minute", "second"),
    "transcript": (
        "say",
        "said",
        "explain",
        "explains",
        "mention",
        "mentions",
        "discuss",
        "talk",
        "talks",
        "describe",
    ),
}


def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]{2,}", text.lower()) if w not in _STOPWORDS]


def _detect_intent(query: str) -> QueryIntent:
    q = query.lower()
    for intent in ("summary", "visual", "timestamp", "transcript"):
        if any(kw in q for kw in _INTENT_KEYWORDS[intent]):  # type: ignore[index]
            return intent  # type: ignore[return-value]
    return "hybrid"


def _fuzzy_overlap(q_tokens: list[str], text: str) -> int:
    """Count distinct snippet words that match a query token (exact or 4-char prefix)."""
    hits = 0
    for w in set(_tokenize(text)):
        for t in q_tokens:
            if w == t or (len(w) >= 4 and len(t) >= 4 and w[:4] == t[:4]):
                hits += 1
                break
    return hits


def _mmss(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _preferred_modality(intent: QueryIntent) -> str | None:
    if intent == "visual":
        return "visual"
    if intent == "transcript":
        return "transcript"
    return None


def mock_search(req: SearchRequest) -> SearchResponse:
    """Synthesize a plausible, query-responsive search response."""
    intent = _detect_intent(req.query)
    q_tokens = _tokenize(req.query)
    pref = _preferred_modality(intent)

    moments = [m for m in _MOMENTS if not req.video_ids or m[0] in req.video_ids]

    scored: list[tuple[float, int, _Moment]] = []
    for m in moments:
        vid, start, _end, modality, snippet = m
        overlap = _fuzzy_overlap(q_tokens, f"{snippet} {_VIDEO_TITLES.get(vid, '')}")
        score = 0.5 + 0.1 * min(overlap, 4)
        if pref and modality == pref:
            score += 0.08
        scored.append((min(score, 0.96), overlap, m))

    best_overlap = max((o for _, o, _ in scored), default=0)
    off_domain = any(tok in _OFF_DOMAIN for tok in q_tokens)
    broad = intent in ("summary", "timestamp")

    # Cheap pre-generation gate: refuse when nothing matches and the query isn't broad.
    if off_domain or (best_overlap == 0 and not broad):
        return SearchResponse(
            query=req.query,
            intent="no_answer",
            answer=NO_ANSWER_MESSAGE,
            refused=True,
            confidence=0.18,
            results=[],
        )

    # Keep matching moments; for broad queries fall back to the strongest few.
    keep = [t for t in scored if t[1] > 0] or sorted(scored, reverse=True)[:4]
    keep.sort(key=lambda t: (t[0], t[1]), reverse=True)
    keep = keep[: req.top_k]

    results: list[SearchResult] = []
    for rank, (score, _overlap, (vid, start, end, modality, snippet)) in enumerate(keep, 1):
        results.append(
            SearchResult(
                rank=rank,
                video_id=vid,
                title=_VIDEO_TITLES[vid],
                start_seconds=start,
                end_seconds=end,
                modality=modality,  # type: ignore[arg-type]
                score=round(score, 3),
                snippet=snippet,
                thumbnail_url=_thumb(vid),
                seek_url=f"{_watch(vid)}?t={int(start)}",
            )
        )

    top = results[0]
    answer = f"{top.snippet} This appears around {_mmss(top.start_seconds)} in “{top.title}”."
    if len(results) > 1:
        second = results[1]
        answer += f" Related: {second.snippet.rstrip('.')} (around {_mmss(second.start_seconds)})."

    return SearchResponse(
        query=req.query,
        rewritten_query=None,
        intent=intent,
        answer=answer,
        refused=False,
        confidence=round(top.score, 3),
        results=results,
    )


# ── In-memory ingestion jobs (admin console) ──────────────────────────


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _ago(minutes: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat(timespec="seconds")


_jobs_lock = Lock()
_job_seq = count(3)
_JOBS: list[Job] = [
    Job(
        id="job_002",
        youtube_url=_watch("as9IYFrTiKc"),
        video_id="as9IYFrTiKc",
        title="A Real Sprint Review Meeting Example",
        status="failed",
        progress=40,
        created_at=_ago(95),
        updated_at=_ago(90),
        error="yt-dlp: video temporarily unavailable (mock)",
    ),
    Job(
        id="job_001",
        youtube_url=_watch("DVtcZQ2QdBg"),
        video_id="DVtcZQ2QdBg",
        title="10 Ways to Build an Unfair Advantage in Your 20s",
        status="completed",
        progress=100,
        created_at=_ago(180),
        updated_at=_ago(168),
        error=None,
    ),
]


def list_jobs() -> JobsResponse:
    with _jobs_lock:
        return JobsResponse(jobs=list(_JOBS))


def add_job(youtube_url: str) -> IngestResponse:
    normalized = normalize_youtube_url(youtube_url)
    now = _now()
    job = Job(
        id=f"job_{next(_job_seq):03d}",
        youtube_url=normalized.youtube_url,
        video_id=normalized.video_id,
        title=None,
        status="queued",
        progress=0,
        created_at=now,
        updated_at=now,
    )
    with _jobs_lock:
        _JOBS.insert(0, job)
    return IngestResponse(job=job)
