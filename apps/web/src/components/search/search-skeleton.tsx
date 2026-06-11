"use client";

import { motion } from "motion/react";

import { viewFade } from "@/lib/motion";

/** Mirrors the results layout while the pipeline retrieves + grounds, so the
 * answer reveal lands in place instead of reflowing the page. */
export function SearchSkeleton() {
  return (
    <motion.div
      {...viewFade}
      role="status"
      aria-label="Searching indexed videos"
      className="grid gap-5 lg:grid-cols-3"
    >
      <div className="flex flex-col gap-4 lg:col-span-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-2">
            <div className="skeleton size-4 rounded-full" />
            <div className="skeleton h-4 w-16" />
          </div>
          <div className="mt-3 flex flex-col gap-2">
            <div className="skeleton h-3.5 w-full" />
            <div className="skeleton h-3.5 w-11/12" />
            <div className="skeleton h-3.5 w-3/5" />
          </div>
        </div>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="flex gap-4 rounded-xl border border-border bg-card p-3"
          >
            <div className="skeleton hidden h-[72px] w-32 shrink-0 rounded-lg sm:block" />
            <div className="flex min-w-0 flex-1 flex-col gap-2 py-0.5">
              <div className="flex items-center gap-2">
                <div className="skeleton h-4 w-20 rounded-full" />
                <div className="skeleton h-4 w-14 rounded-full" />
              </div>
              <div className="skeleton h-3.5 w-2/3" />
              <div className="skeleton h-3 w-full" />
            </div>
          </div>
        ))}
      </div>
      <div className="lg:col-span-1">
        <div className="skeleton aspect-video w-full rounded-xl" />
      </div>
      <span className="sr-only">Searching…</span>
    </motion.div>
  );
}
