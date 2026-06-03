"use client";

import {
  Clock,
  Database,
  FileText,
  ImageIcon,
  Minus,
  Plus,
  type LucideIcon,
} from "lucide-react";
import Image from "next/image";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { durationLabel } from "@/lib/format";
import type { DemoVideo } from "@/lib/types";
import { cn } from "@/lib/utils";

const numberFormatter = new Intl.NumberFormat("en-US");

export function VideoLibrary({ videos }: { videos: DemoVideo[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const indexed = videos.filter((video) => video.indexed);
  const vectorTotal = indexed.reduce(
    (total, video) => total + (video.artifact_stats?.indexed_vectors ?? 0),
    0,
  );

  if (videos.length === 0) return null;

  function toggle(videoId: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(videoId)) next.delete(videoId);
      else next.add(videoId);
      return next;
    });
  }

  return (
    <section className="mt-2 flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h2 className="text-sm font-semibold">Indexed library</h2>
        <p className="text-xs text-muted-foreground">
          {indexed.length} videos · {numberFormatter.format(vectorTotal)} vectors
        </p>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {videos.map((video) => {
          const isExpanded = expanded.has(video.id);
          const panelId = `video-details-${video.id}`;
          return (
            <article
              key={video.id}
              className={cn(
                "overflow-hidden rounded-lg border bg-card text-sm shadow-xs",
                isExpanded ? "border-primary/35" : "border-border",
              )}
            >
              <div className="grid grid-cols-[5rem_minmax(0,1fr)_auto] items-center gap-3 p-3">
                <Image
                  src={video.thumbnail_url}
                  alt=""
                  width={80}
                  height={48}
                  className="h-12 w-20 rounded-md object-cover"
                />
                <div className="min-w-0">
                  <div className="truncate font-medium">{video.title}</div>
                  <div className="mt-0.5 flex min-w-0 flex-wrap gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
                    <span className="truncate">{video.author}</span>
                    {video.domain && <span>{video.domain}</span>}
                    <span>{durationLabel(video.duration_seconds)}</span>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  aria-expanded={isExpanded}
                  aria-controls={panelId}
                  title={isExpanded ? "Hide video details" : "Show video details"}
                  onClick={() => toggle(video.id)}
                >
                  {isExpanded ? <Minus /> : <Plus />}
                  <span className="sr-only">
                    {isExpanded ? "Hide video details" : "Show video details"}
                  </span>
                </Button>
              </div>

              {isExpanded && (
                <div id={panelId} className="border-t border-border px-3 py-3">
                  {video.artifact_stats ? (
                    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <LibraryStat
                        icon={ImageIcon}
                        label="Frames"
                        value={formatCount(video.artifact_stats.visual_frames)}
                      />
                      <LibraryStat
                        icon={FileText}
                        label="Chunks"
                        value={formatCount(video.artifact_stats.transcript_chunks)}
                      />
                      <LibraryStat
                        icon={Database}
                        label="Vectors"
                        value={formatCount(video.artifact_stats.indexed_vectors)}
                      />
                      <LibraryStat
                        icon={Clock}
                        label="Frame step"
                        value={
                          video.artifact_stats.frame_interval_seconds
                            ? `${video.artifact_stats.frame_interval_seconds}s`
                            : "Unknown"
                        }
                      />
                      <div className="col-span-2 text-xs text-muted-foreground sm:col-span-4">
                        {formatCount(video.artifact_stats.transcript_segments)} transcript
                        segments · transcript and visual indexes populated
                      </div>
                    </dl>
                  ) : (
                    <p className="text-xs text-muted-foreground">Artifact stats unavailable.</p>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function LibraryStat({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/35 p-2">
      <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </dt>
      <dd className="mt-1 font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

function formatCount(value: number | null): string {
  return value === null ? "Unknown" : numberFormatter.format(value);
}
