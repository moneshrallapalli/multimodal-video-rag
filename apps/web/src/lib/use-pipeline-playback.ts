import { useEffect, useState } from "react";

import type { PipelineEvent } from "./types";

/** Minimum dwell per event when the backend delivers a burst (Lambda buffers SSE). */
const STARTED_STEP_MS = 200;
const TERMINAL_STEP_MS = 480;

function stepDelay(event: PipelineEvent): number {
  return event.status === "started" ? STARTED_STEP_MS : TERMINAL_STEP_MS;
}

/** Reveal pipeline events one at a time so the graph advances step-by-step. */
export function usePipelineEventPlayback(
  streamEvents: PipelineEvent[],
  { enabled = true }: { enabled?: boolean } = {},
) {
  const runKey = streamEvents[0]?.run_id ?? "idle";
  const [playback, setPlayback] = useState({ runKey, visibleCount: 0 });

  if (playback.runKey !== runKey) {
    setPlayback({ runKey, visibleCount: 0 });
  }

  useEffect(() => {
    if (!enabled) return;
    if (playback.visibleCount >= streamEvents.length) return;

    const next = streamEvents[playback.visibleCount];
    const timer = window.setTimeout(() => {
      setPlayback((current) => ({
        runKey: current.runKey,
        visibleCount: current.visibleCount + 1,
      }));
    }, stepDelay(next));

    return () => window.clearTimeout(timer);
  }, [enabled, playback.visibleCount, runKey, streamEvents]);

  const displayedEvents = enabled
    ? streamEvents.slice(0, playback.visibleCount)
    : streamEvents;
  const playing = enabled && playback.visibleCount < streamEvents.length;

  return { displayedEvents, playing };
}
