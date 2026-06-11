"use client";

import { AnimatePresence, motion } from "motion/react";

import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STYLES: Record<JobStatus, string> = {
  queued: "bg-muted text-muted-foreground",
  downloading: "bg-primary/10 text-primary",
  transcribing: "bg-primary/10 text-primary",
  embedding: "bg-primary/10 text-primary",
  completed: "bg-primary text-primary-foreground",
  failed: "bg-red-100 text-red-700",
};

const ACTIVE: ReadonlySet<JobStatus> = new Set(["downloading", "transcribing", "embedding"]);

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return (
    <AnimatePresence mode="popLayout" initial={false}>
      {/* Keyed by status so each pipeline stage crossfades in as polling advances. */}
      <motion.span
        key={status}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className="inline-flex"
      >
        <Badge variant="secondary" className={cn("capitalize", STYLES[status])}>
          {ACTIVE.has(status) && (
            <span className="relative mr-0.5 flex size-1.5" aria-hidden>
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />
              <span className="relative inline-flex size-1.5 rounded-full bg-current" />
            </span>
          )}
          {status}
        </Badge>
      </motion.span>
    </AnimatePresence>
  );
}
