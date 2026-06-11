/** Shared motion vocabulary. Motion conveys pipeline state, never decorates.
 *
 * Durations follow the 100/300/500 rule: ~150ms feedback, ~250ms state
 * changes, ~450ms for the one hero reveal (search → answer). Exits run at
 * ~75% of the matching entrance.
 */
import type { Variants } from "motion/react";

export const EASE_OUT_QUINT = [0.22, 1, 0.36, 1] as const;
export const EASE_OUT_EXPO = [0.16, 1, 0.3, 1] as const;

/** Hero reveal: parent staggers answer → proofs → player in evidence order. */
export const revealContainer: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.055, delayChildren: 0.05 },
  },
};

export const revealItem: Variants = {
  hidden: { opacity: 0, y: 14, filter: "blur(4px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.45, ease: EASE_OUT_QUINT },
  },
};

/** Utility fade for view swaps (empty ↔ loading ↔ results). */
export const viewFade = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: EASE_OUT_QUINT } },
  exit: { opacity: 0, transition: { duration: 0.15, ease: "easeOut" as const } },
};

/** Expand/collapse for detail panels (library stats, methodology). */
export const expandPanel = {
  initial: { height: 0, opacity: 0 },
  animate: {
    height: "auto" as const,
    opacity: 1,
    transition: { duration: 0.3, ease: EASE_OUT_QUINT },
  },
  exit: {
    height: 0,
    opacity: 0,
    transition: { duration: 0.22, ease: "easeOut" as const },
  },
};
