"use client";

import { ChevronDown, Check } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { DemoVideo } from "@/lib/types";
import { cn } from "@/lib/utils";

export function VideoFilter({
  videos,
  value,
  onChange,
  className,
}: {
  videos: DemoVideo[];
  value: string[];
  onChange: (ids: string[]) => void;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (videos.length === 0) return null;

  const indexed = videos.filter((v) => v.indexed);

  function toggle(id: string) {
    if (value.includes(id)) {
      onChange(value.filter((v) => v !== id));
    } else {
      onChange([...value, id]);
    }
  }

  const label =
    value.length === 0
      ? `All indexed videos (${indexed.length})`
      : value.length === 1
        ? videos.find((v) => v.id === value[0])?.title ?? "1 video"
        : `${value.length} videos selected`;

  return (
    <div ref={ref} className={cn("relative flex min-w-0 flex-col gap-1", className)}>
      <span className="text-xs font-medium text-muted-foreground">Video scope</span>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex h-11 w-full items-center justify-between rounded-lg border border-border bg-card px-3 text-sm font-medium text-foreground shadow-xs outline-none transition-colors hover:border-primary/40 focus:border-primary focus:ring-3 focus:ring-ring/30"
        aria-label="Video filter"
        aria-expanded={open}
      >
        <span className="truncate">{label}</span>
        <ChevronDown
          className={cn(
            "ml-2 size-4 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div className="absolute top-full z-50 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
          <button
            type="button"
            onClick={() => onChange([])}
            className={cn(
              "flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-muted/50",
              value.length === 0 && "font-medium text-primary",
            )}
          >
            <span
              className={cn(
                "flex size-4 shrink-0 items-center justify-center rounded border",
                value.length === 0
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border",
              )}
            >
              {value.length === 0 && <Check className="size-3" />}
            </span>
            All indexed videos ({indexed.length})
          </button>

          <div className="border-t border-border" />

          {videos.map((video) => {
            const selected = value.includes(video.id);
            return (
              <button
                key={video.id}
                type="button"
                disabled={!video.indexed}
                onClick={() => toggle(video.id)}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-muted/50",
                  !video.indexed && "cursor-not-allowed opacity-50",
                )}
              >
                <span
                  className={cn(
                    "flex size-4 shrink-0 items-center justify-center rounded border",
                    selected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border",
                  )}
                >
                  {selected && <Check className="size-3" />}
                </span>
                <span className="truncate">
                  {video.title}
                  {!video.indexed ? " — not indexed yet" : ""}
                </span>
              </button>
            );
          })}
        </div>
      )}

      <span className="truncate text-xs text-muted-foreground">
        {value.length === 0
          ? "Corpus-wide retrieval"
          : value.length === 1
            ? (videos.find((v) => v.id === value[0])?.author ?? "")
            : "Multi-video retrieval"}
      </span>
    </div>
  );
}
