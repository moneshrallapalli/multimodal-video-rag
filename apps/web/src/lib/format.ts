/** Small display helpers shared across surfaces. */

/** Seconds → `m:ss` (e.g. 612 → "10:12"). */
export function mmss(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** 0–1 score → integer percent string (e.g. 0.842 → "84%"). */
export function pct(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/** Truncate to `max` chars with an ellipsis. */
export function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max - 1).trimEnd()}…`;
}
