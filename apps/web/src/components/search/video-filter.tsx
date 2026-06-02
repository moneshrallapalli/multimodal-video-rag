"use client";

import type { DemoVideo } from "@/lib/types";
import { truncate } from "@/lib/format";
import { cn } from "@/lib/utils";

function FilterChip({
  active,
  disabled = false,
  onClick,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "rounded-full border px-3 py-1 text-xs transition-colors",
        disabled
          ? "cursor-not-allowed border-border bg-muted text-muted-foreground/60"
          : active
            ? "border-primary bg-primary/10 font-medium text-primary"
            : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

export function VideoFilter({
  videos,
  value,
  onChange,
}: {
  videos: DemoVideo[];
  value: string | null;
  onChange: (id: string | null) => void;
}) {
  if (videos.length === 0) return null;
  const indexedCount = videos.filter((v) => v.indexed).length;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-1 text-xs font-medium text-muted-foreground">Filter:</span>
      <FilterChip active={value === null} onClick={() => onChange(null)}>
        {indexedCount === 1 ? "Indexed video" : "All indexed"}
      </FilterChip>
      {videos.map((v) => (
        <FilterChip
          key={v.id}
          active={value === v.id}
          disabled={!v.indexed}
          onClick={() => {
            if (v.indexed) onChange(v.id);
          }}
        >
          {truncate(v.title, 26)}
          {!v.indexed ? " · not indexed yet" : ""}
        </FilterChip>
      ))}
    </div>
  );
}
