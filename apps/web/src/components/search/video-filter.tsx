"use client";

import { ChevronDown } from "lucide-react";

import type { DemoVideo } from "@/lib/types";
import { cn } from "@/lib/utils";

export function VideoFilter({
  videos,
  value,
  onChange,
  className,
}: {
  videos: DemoVideo[];
  value: string | null;
  onChange: (id: string | null) => void;
  className?: string;
}) {
  if (videos.length === 0) return null;

  const indexed = videos.filter((v) => v.indexed);
  const selected = value ? videos.find((v) => v.id === value) : null;

  return (
    <label className={cn("flex min-w-0 flex-col gap-1", className)}>
      <span className="text-xs font-medium text-muted-foreground">Video scope</span>
      <span className="relative block">
        <select
          value={value ?? "all"}
          onChange={(event) =>
            onChange(event.target.value === "all" ? null : event.target.value)
          }
          className="h-11 w-full appearance-none rounded-lg border border-border bg-card px-3 pr-9 text-sm font-medium text-foreground shadow-xs outline-none transition-colors hover:border-primary/40 focus:border-primary focus:ring-3 focus:ring-ring/30"
          aria-label="Video filter"
        >
          <option value="all">All indexed videos ({indexed.length})</option>
          {videos.map((video) => (
            <option key={video.id} value={video.id} disabled={!video.indexed}>
              {video.title}
              {!video.indexed ? " - not indexed yet" : ""}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground" />
      </span>
      <span className="truncate text-xs text-muted-foreground">
        {selected ? selected.author : "Corpus-wide retrieval"}
      </span>
    </label>
  );
}
