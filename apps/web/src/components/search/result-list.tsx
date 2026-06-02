"use client";

import type { SearchResult } from "@/lib/types";

import { ResultCard } from "./result-card";

export function ResultList({
  results,
  activeKey,
  onSeek,
}: {
  results: SearchResult[];
  activeKey: string | null;
  onSeek: (r: SearchResult) => void;
}) {
  return (
    <div className="flex flex-col gap-2.5">
      {results.map((r) => (
        <ResultCard
          key={`${r.video_id}-${r.start_seconds}-${r.rank}`}
          result={r}
          active={activeKey === `${r.video_id}-${r.start_seconds}`}
          onSeek={onSeek}
        />
      ))}
    </div>
  );
}
