"use client";

import { motion, type Variants } from "motion/react";

import type { SearchResult } from "@/lib/types";

import { ResultCard } from "./result-card";

/** Proofs cascade in citation order beneath the answer; the per-card delay is
 * capped so ten results never take longer than ~half a second total. */
const listStagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

export function ResultList({
  results,
  activeKey,
  onSeek,
}: {
  results: SearchResult[];
  activeKey: string | null;
  onSeek: (r: SearchResult) => void;
}) {
  return (
    <motion.div variants={listStagger} className="flex flex-col gap-2.5">
      {results.map((r) => (
        <ResultCard
          key={`${r.video_id}-${r.start_seconds}-${r.rank}`}
          result={r}
          active={activeKey === `${r.video_id}-${r.start_seconds}`}
          onSeek={onSeek}
        />
      ))}
    </motion.div>
  );
}
