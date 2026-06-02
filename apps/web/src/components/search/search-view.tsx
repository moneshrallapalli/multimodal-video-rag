"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { DemoVideo, SearchResponse, SearchResult } from "@/lib/types";

import { AnswerPanel } from "./answer-panel";
import { ResultList } from "./result-list";
import { SearchBar } from "./search-bar";
import { VideoFilter } from "./video-filter";
import { YouTubePlayer } from "./youtube-player";

// Curated demo prompts; the last one trips the no-answer / refusal path.
const EXAMPLES = [
  "What does she say about fear and self sabotage?",
  "How does comfort relate to self sabotage?",
  "When does she recommend starting?",
  "today's weather",
];

type Seek = { videoId: string; seconds: number; title: string };

export function SearchView() {
  const [videos, setVideos] = useState<DemoVideo[]>([]);
  const [videoFilter, setVideoFilter] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [seek, setSeek] = useState<Seek | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .videos()
      .then(setVideos)
      .catch(() =>
        setError("Could not load the demo library. Is the API running on :8000?"),
      );
  }, []);

  async function runSearch(q?: string) {
    const term = (q ?? query).trim();
    if (!term) return;
    if (q !== undefined) setQuery(q);
    setLoading(true);
    setError(null);
    try {
      const r = await api.search({ query: term, video_id: videoFilter });
      setResponse(r);
      setSeek(
        r.results.length
          ? {
              videoId: r.results[0].video_id,
              seconds: r.results[0].start_seconds,
              title: r.results[0].title,
            }
          : null,
      );
    } catch {
      setError("Could not reach the search API. Make sure the backend is running on :8000.");
    } finally {
      setLoading(false);
    }
  }

  function onSeek(r: SearchResult) {
    setSeek({ videoId: r.video_id, seconds: r.start_seconds, title: r.title });
  }

  const activeKey = seek ? `${seek.videoId}-${seek.seconds}` : null;
  const indexedCount = videos.filter((v) => v.indexed).length;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3">
        <SearchBar
          value={query}
          onChange={setQuery}
          onSubmit={() => runSearch()}
          loading={loading}
        />
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-xs font-medium text-muted-foreground">Try:</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => runSearch(ex)}
              className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
            >
              {ex}
            </button>
          ))}
        </div>
        <VideoFilter videos={videos} value={videoFilter} onChange={setVideoFilter} />
      </div>

      {error && (
        <div className="rounded-lg border border-amber-300/60 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {error}
        </div>
      )}

      {response ? (
        <div className="grid gap-5 lg:grid-cols-3">
          <div className="order-last flex flex-col gap-4 lg:order-first lg:col-span-2">
            <AnswerPanel response={response} />
            {response.results.length > 0 && (
              <ResultList results={response.results} activeKey={activeKey} onSeek={onSeek} />
            )}
          </div>
          <div className="lg:col-span-1">
            <div className="lg:sticky lg:top-20">
              <YouTubePlayer
                videoId={seek?.videoId ?? null}
                startSeconds={seek?.seconds ?? 0}
                title={seek?.title}
              />
              {seek && (
                <p className="mt-2 line-clamp-1 text-xs text-muted-foreground">
                  Now playing: {seek.title}
                </p>
              )}
            </div>
          </div>
        </div>
      ) : (
        !error && (
          <p className="text-sm text-muted-foreground">
            Search the {indexedCount || "seed"} indexed video
            {indexedCount === 1 ? "" : "s"} by what was{" "}
            <span className="text-foreground">said</span> or{" "}
            <span className="text-foreground">shown</span>. Results jump the player to the
            exact moment.
          </p>
        )
      )}
    </div>
  );
}
