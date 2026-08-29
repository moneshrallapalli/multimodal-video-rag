"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { GitBranch, LoaderCircle, RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { revealContainer, revealItem, viewFade } from "@/lib/motion";
import { usePipelineEventPlayback } from "@/lib/use-pipeline-playback";
import type { DemoVideo, PipelineEvent, SearchResponse, SearchResult } from "@/lib/types";

import { AnswerPanel } from "./answer-panel";
import { PipelinePanel } from "./pipeline-panel";
import { ResultList } from "./result-list";
import { SearchBar } from "./search-bar";
import { VideoLibrary } from "./video-library";
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
type Surface = "pipeline" | "answer";

const SURFACE_HINT: Record<Surface, string> = {
  pipeline: "How the query ran — live graph, node detail, orchestrator log",
  answer: "What you got back — grounded answer, citations, and video player",
};

export function SearchView() {
  const [videos, setVideos] = useState<DemoVideo[]>([]);
  const [videoFilter, setVideoFilter] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [surface, setSurface] = useState<Surface>("pipeline");
  const [seek, setSeek] = useState<Seek | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const reduceMotion = useReducedMotion() ?? false;
  const { displayedEvents, playing } = usePipelineEventPlayback(events, {
    enabled: !reduceMotion,
  });
  const pipelineRunning = loading || playing;

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
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    setResponse(null);
    setEvents([]);
    setSeek(null);
    setSurface("pipeline");
    const request = { query: term, video_ids: videoFilter.length ? videoFilter : null };
    try {
      const r = await api.searchStream(request, {
        onEvent: (event) => setEvents((prev) => [...prev, event]),
        signal: controller.signal,
      });
      applyResponse(r);
    } catch (err) {
      if (isAbort(err)) return;
      try {
        const r = await api.search(request);
        applyResponse(r);
      } catch {
        setError("Could not reach the search API. Make sure the backend is running on :8000.");
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  function applyResponse(r: SearchResponse) {
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
  }

  function resetSearch() {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
    setResponse(null);
    setEvents([]);
    setSeek(null);
    setError(null);
    setSurface("pipeline");
  }

  function onSeek(r: SearchResult) {
    setSeek({ videoId: r.video_id, seconds: r.start_seconds, title: r.title });
  }

  const activeKey = seek ? `${seek.videoId}-${seek.seconds}` : null;
  const indexedCount = videos.filter((v) => v.indexed).length;
  const hasActiveSession = loading || events.length > 0 || Boolean(response);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_16rem] lg:items-end">
          <SearchBar
            value={query}
            onChange={setQuery}
            onSubmit={() => runSearch()}
            loading={loading}
          />
          <VideoFilter videos={videos} value={videoFilter} onChange={setVideoFilter} />
        </div>
        {!hasActiveSession ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-medium text-muted-foreground">Try:</span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => runSearch(ex)}
                className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground shadow-sm transition-[color,border-color,transform,box-shadow] duration-150 hover:border-primary/40 hover:text-foreground hover:shadow active:scale-[0.97]"
              >
                {ex}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <AnimatePresence mode="wait" initial={false}>
        {hasActiveSession ? (
          <motion.div
            key="run"
            variants={revealContainer}
            initial="hidden"
            animate="show"
            className="flex flex-col gap-4"
          >
            <div className="flex flex-col gap-3 rounded-xl border border-border/80 bg-card/60 p-3 shadow-sm backdrop-blur-sm sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4">
              <div className="min-w-0">
                <div className="inline-flex rounded-lg border border-border bg-muted/50 p-0.5">
                  <SurfaceTab
                    label="Pipeline"
                    icon={GitBranch}
                    active={surface === "pipeline"}
                    onClick={() => setSurface("pipeline")}
                  />
                  <SurfaceTab
                    label="Answer"
                    icon={Sparkles}
                    active={surface === "answer"}
                    onClick={() => setSurface("answer")}
                  />
                </div>
                <p className="mt-2 text-xs text-muted-foreground">{SURFACE_HINT[surface]}</p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="shrink-0 self-start sm:self-center"
                onClick={resetSearch}
              >
                <RotateCcw data-icon="inline-start" />
                New search
              </Button>
            </div>

            {surface === "pipeline" ? (
              <PipelinePanel
                key={events[0]?.run_id ?? "idle"}
                events={displayedEvents}
                running={pipelineRunning}
              />
            ) : response ? (
              <div className="grid gap-5 lg:grid-cols-3">
                <div className="flex flex-col gap-4 lg:col-span-2">
                  <AnswerPanel response={response} />
                  {response.results.length > 0 ? (
                    <div>
                      <h2 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                        Citations
                      </h2>
                      <ResultList
                        results={response.results}
                        activeKey={activeKey}
                        onSeek={onSeek}
                      />
                    </div>
                  ) : null}
                </div>
                <motion.div variants={revealItem} className="lg:col-span-1">
                  <div className="lg:sticky lg:top-20">
                    <h2 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                      Video proof
                    </h2>
                    <YouTubePlayer
                      videoId={seek?.videoId ?? null}
                      startSeconds={seek?.seconds ?? 0}
                      title={seek?.title}
                    />
                    {seek ? (
                      <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                        Now playing: {seek.title}
                      </p>
                    ) : (
                      <p className="mt-2 text-xs text-muted-foreground">
                        No video moment to play for this result.
                      </p>
                    )}
                  </div>
                </motion.div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center rounded-2xl border border-border bg-card px-6 py-14 text-center shadow-sm">
                <LoaderCircle className="size-8 animate-spin text-primary" aria-hidden />
                <p className="mt-3 text-sm font-medium">Generating grounded answer…</p>
                <p className="mt-1 max-w-sm text-xs text-muted-foreground">
                  Retrieval and synthesis are still running. Switch to Pipeline to watch progress.
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="mt-4"
                  onClick={() => setSurface("pipeline")}
                >
                  <GitBranch data-icon="inline-start" />
                  Watch pipeline
                </Button>
              </div>
            )}
          </motion.div>
        ) : !error ? (
          <motion.div key="empty" {...viewFade} className="flex flex-col gap-5">
            <p className="text-sm text-muted-foreground">
              Search the {indexedCount || "seed"} indexed video
              {indexedCount === 1 ? "" : "s"} by what was{" "}
              <span className="text-foreground">said</span> or{" "}
              <span className="text-foreground">shown</span>. Results jump the player to the exact
              moment.
            </p>
            <VideoLibrary videos={videos} />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function SurfaceTab({
  label,
  icon: Icon,
  active,
  onClick,
}: {
  label: string;
  icon: typeof GitBranch;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? "inline-flex items-center gap-1.5 rounded-md bg-card px-3 py-1.5 text-xs font-medium text-foreground shadow-sm"
          : "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
      }
    >
      <Icon className="size-3.5" aria-hidden />
      {label}
    </button>
  );
}

function isAbort(err: unknown): boolean {
  return err instanceof DOMException
    ? err.name === "AbortError"
    : err instanceof Error && err.name === "AbortError";
}
