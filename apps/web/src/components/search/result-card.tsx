"use client";

import { Clock, ExternalLink, Play } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { mmss, pct } from "@/lib/format";
import type { SearchResult } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ModalityBadge } from "./modality-badge";

export function ResultCard({
  result,
  active,
  onSeek,
}: {
  result: SearchResult;
  active: boolean;
  onSeek: (r: SearchResult) => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSeek(result)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSeek(result);
        }
      }}
      className={cn(
        "group flex cursor-pointer gap-4 rounded-xl border bg-card p-3 transition-colors hover:border-primary/50 hover:bg-accent/40",
        active ? "border-primary ring-1 ring-primary/30" : "border-border",
      )}
    >
      <div className="relative hidden h-[72px] w-32 shrink-0 overflow-hidden rounded-lg bg-muted sm:block">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={result.thumbnail_url} alt="" className="h-full w-full object-cover" />
        <span className="absolute right-1 bottom-1 rounded bg-black/75 px-1 text-[10px] font-medium text-white">
          {mmss(result.start_seconds)}
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <ModalityBadge modality={result.modality} />
          <Badge variant="outline" className="gap-1 font-normal text-muted-foreground">
            <Clock className="size-3" /> {mmss(result.start_seconds)}
          </Badge>
          <span className="ml-auto text-xs font-medium text-primary">
            {pct(result.score)} match
          </span>
        </div>
        <p className="mt-1.5 line-clamp-1 text-sm font-medium">{result.title}</p>
        <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{result.snippet}</p>
        <div className="mt-2 flex items-center gap-2">
          <Button
            size="sm"
            className="h-7 gap-1 px-2.5"
            onClick={(e) => {
              e.stopPropagation();
              onSeek(result);
            }}
          >
            <Play className="size-3.5" /> Play {mmss(result.start_seconds)}
          </Button>
          <a
            href={result.seek_url}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs text-muted-foreground hover:text-foreground"
          >
            YouTube <ExternalLink className="size-3" />
          </a>
        </div>
      </div>
    </div>
  );
}
