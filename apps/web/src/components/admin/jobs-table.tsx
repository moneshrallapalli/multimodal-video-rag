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

import { JobStatusBadge } from "./job-status-badge";

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-muted">
      <div className="h-full rounded-full bg-primary" style={{ width: `${value}%` }} />
    </div>
  );
}

export function JobsTable({ jobs }: { jobs: Job[] }) {
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold">Ingestion jobs</h2>
      <div className="overflow-hidden rounded-xl border border-border bg-card">
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
              jobs.map((j) => (
                <TableRow key={j.id}>
                  <TableCell className="max-w-[260px]">
                    <div className="truncate font-medium">{j.title ?? j.youtube_url}</div>
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
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
