"use client";

import { Clock, ExternalLink, Play } from "lucide-react";
import { motion } from "motion/react";
import Image from "next/image";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { mmss } from "@/lib/format";
import { EASE_OUT_QUINT, revealItem } from "@/lib/motion";
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
    <motion.div
      variants={revealItem}
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
        "group relative flex cursor-pointer gap-4 rounded-2xl border border-border bg-card p-3 shadow-sm transition-[border-color,box-shadow,background-color] duration-200 hover:border-primary/40 hover:shadow-md",
        active && "bg-accent/30",
      )}
    >
      {/* The ring glides to whichever proof is playing (shared layout id). */}
      {active && (
        <motion.div
          layoutId="active-proof-ring"
          transition={{ duration: 0.3, ease: EASE_OUT_QUINT }}
          className="pointer-events-none absolute -inset-px rounded-xl border-2 border-primary"
        />
      )}
      <div className="relative hidden h-[72px] w-32 shrink-0 overflow-hidden rounded-lg bg-muted sm:block">
        <Image
          src={result.thumbnail_url}
          alt=""
          fill
          sizes="128px"
          className="object-cover transition-transform duration-300 ease-out group-hover:scale-[1.04]"
        />
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
          <span className="ml-auto text-xs font-medium text-primary">Proof #{result.rank}</span>
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
            className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            YouTube <ExternalLink className="size-3" />
          </a>
        </div>
      </div>
    </motion.div>
  );
}
