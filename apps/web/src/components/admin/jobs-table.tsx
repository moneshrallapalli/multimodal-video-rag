"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Job } from "@/lib/types";
import { cn } from "@/lib/utils";

import { JobStatusBadge } from "./job-status-badge";

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-muted">
      <div
        className="ease-out-quint h-full rounded-full bg-primary transition-[width] duration-700"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

export function JobsTable({
  jobs,
  selectedId,
  onSelect,
}: {
  jobs: Job[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold">Ingestion jobs</h2>
      <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Video</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-28">Progress</TableHead>
              <TableHead>Updated</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {jobs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="py-6 text-center text-sm text-muted-foreground">
                  No jobs yet. Queue a YouTube URL above.
                </TableCell>
              </TableRow>
            ) : (
              jobs.map((j) => {
                const selected = j.id === selectedId;
                return (
                  <TableRow
                    key={j.id}
                    data-state={selected ? "selected" : undefined}
                    className={cn(
                      "animate-in fade-in slide-in-from-top-1 cursor-pointer duration-300 ease-out",
                      selected && "bg-muted/70",
                    )}
                    onClick={() => onSelect(j.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onSelect(j.id);
                      }
                    }}
                    tabIndex={0}
                    aria-selected={selected}
                  >
                    <TableCell className="max-w-[260px]">
                      <div className="truncate font-medium">{j.title ?? j.youtube_url}</div>
                      {j.stage ? (
                        <div className="truncate font-mono text-[11px] text-muted-foreground">
                          {j.stage}
                        </div>
                      ) : null}
                      {j.error && <div className="truncate text-xs text-red-600">{j.error}</div>}
                    </TableCell>
                    <TableCell>
                      <JobStatusBadge status={j.status} />
                    </TableCell>
                    <TableCell>
                      <ProgressBar value={j.progress} />
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {fmtTime(j.updated_at)}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
