"use client";

import { MotionConfig } from "motion/react";

/** Honors the OS-level reduced-motion preference for all JS-driven motion. */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
