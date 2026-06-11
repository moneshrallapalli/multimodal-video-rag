"use client";

import { PlayCircle } from "lucide-react";
import { motion } from "motion/react";

/**
 * Seeks by remounting the embed iframe whenever the video or start time changes
 * (the `key` forces a fresh element with `?start=`), which is the most reliable
 * cross-browser jump-to-timestamp without the YouTube IFrame JS API.
 */
export function YouTubePlayer({
  videoId,
  startSeconds,
  title,
}: {
  videoId: string | null;
  startSeconds: number;
  title?: string;
}) {
  if (!videoId) {
    return (
      <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-muted/40 px-4 text-center text-sm text-muted-foreground">
        <PlayCircle className="animate-float-gentle size-8 opacity-50" />
        <p>Run a search and pick a result to play that moment here.</p>
      </div>
    );
  }
  const start = Math.floor(startSeconds);
  const src = `https://www.youtube.com/embed/${videoId}?start=${start}&autoplay=1&rel=0`;
  return (
    <div className="aspect-video w-full overflow-hidden rounded-xl border border-border bg-black shadow-sm">
      {/* Soften the black flash of the iframe remount on every seek. */}
      <motion.div
        key={`${videoId}-${start}`}
        initial={{ opacity: 0.3 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="h-full w-full"
      >
        <iframe
          src={src}
          title={title ?? "YouTube player"}
          className="h-full w-full"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
        />
      </motion.div>
    </div>
  );
}
