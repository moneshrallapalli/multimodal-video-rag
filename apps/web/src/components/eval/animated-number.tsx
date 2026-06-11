"use client";

import { animate, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { EASE_OUT_QUINT } from "@/lib/motion";

/** Counts up to `value` on mount and tweens between values on change.
 * Renders the final value on the server / first paint, so metrics stay real
 * for no-JS readers; reduced motion snaps instantly. */
export function AnimatedNumber({
  value,
  format = (v: number) => String(Math.round(v)),
  duration = 0.6,
}: {
  value: number;
  format?: (v: number) => string;
  duration?: number;
}) {
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(value);
  const prev = useRef(0);

  useEffect(() => {
    if (reduce) {
      prev.current = value;
      return;
    }
    const controls = animate(prev.current, value, {
      duration,
      ease: EASE_OUT_QUINT,
      onUpdate: setDisplay,
    });
    prev.current = value;
    return () => controls.stop();
  }, [value, reduce, duration]);

  return <span className="tabular-nums">{format(reduce ? value : display)}</span>;
}
