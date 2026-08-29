"use client";

import { useLayoutEffect, useMemo, useRef, useState } from "react";

import type { CockpitColumn, CockpitRuntime } from "@/lib/cockpit";
import { cn } from "@/lib/utils";

type Point = { x: number; y: number };

export function CockpitGraph<Id extends string>({
  columns,
  edges,
  nodes,
  selectedId,
  onSelect,
  reduceMotion,
  dimColumn,
  isLiveEdge,
  columnCountClass = "grid-cols-5",
}: {
  columns: CockpitColumn<Id>[];
  edges: [Id, Id][];
  nodes: Record<Id, CockpitRuntime>;
  selectedId: Id | null;
  onSelect: (id: Id) => void;
  reduceMotion: boolean;
  dimColumn?: (columnId: string) => boolean;
  isLiveEdge?: (from: Id, to: Id) => boolean;
  columnCountClass?: string;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const anchorRefs = useRef<Partial<Record<Id, HTMLSpanElement | null>>>({});
  const [points, setPoints] = useState<Partial<Record<Id, Point>>>({});
  const pulses = useMemo(() => {
    if (reduceMotion) return [];
    const next: Array<{ id: string; d: string }> = [];
    for (const [from, to] of edges) {
      const live =
        isLiveEdge?.(from, to) ??
        (nodes[from].status !== "idle" && nodes[to].status !== "idle");
      if (!live) continue;
      const d = edgePath(points[from], points[to]);
      if (!d) continue;
      next.push({ id: `${from}-${to}-${nodes[to].status}`, d });
    }
    return next;
  }, [edges, isLiveEdge, nodes, points, reduceMotion]);

  useLayoutEffect(() => {
    const measure = () => {
      const root = rootRef.current?.getBoundingClientRect();
      if (!root) return;
      const next: Partial<Record<Id, Point>> = {};
      for (const [id, el] of Object.entries(anchorRefs.current)) {
        if (!el) continue;
        const box = (el as HTMLSpanElement).getBoundingClientRect();
        next[id as Id] = {
          x: box.left - root.left + box.width / 2,
          y: box.top - root.top + box.height / 2,
        };
      }
      setPoints(next);
    };
    const observer = new ResizeObserver(measure);
    if (rootRef.current) observer.observe(rootRef.current);
    window.addEventListener("resize", measure);
    measure();
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [nodes]);

  return (
    <div ref={rootRef} className="relative min-h-[22rem] min-w-[52rem]">
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
        aria-hidden
      >
        {edges.map(([from, to]) => {
          const d = edgePath(points[from], points[to]);
          if (!d) return null;
          const live =
            isLiveEdge?.(from, to) ??
            (nodes[from].status !== "idle" && nodes[to].status !== "idle");
          const failed =
            nodes[to].status === "failed" ||
            nodes[to].status === "refused" ||
            nodes[from].status === "failed" ||
            nodes[from].status === "refused";
          return (
            <path
              key={`${from}-${to}`}
              d={d}
              fill="none"
              className={cn(
                "pipe-edge",
                live && "pipe-edge-live",
                failed && live && "pipe-edge-fail",
              )}
            />
          );
        })}
        {pulses.map((pulse) => (
          <circle
            key={pulse.id}
            r="3.5"
            className="pipe-pulse-dot"
            style={{ offsetPath: `path('${pulse.d}')` }}
          />
        ))}
      </svg>

      <div className={cn("relative grid h-full gap-2 px-1 pt-1", columnCountClass)}>
        {columns.map((column) => (
          <div
            key={column.id}
            className={cn(
              "flex flex-col items-center",
              dimColumn?.(column.id) && "opacity-40",
            )}
          >
            <div className={cn("pipe-col-label", `pipe-tint-${column.tint}`)}>{column.label}</div>
            <div
              className={cn(
                "mt-3 flex w-full flex-1 flex-col items-center",
                column.nodes.length === 2 ? "justify-center gap-10" : "justify-between gap-4",
              )}
            >
              {column.nodes.map((node) => {
                const runtime = nodes[node.id];
                const selected = selectedId === node.id;
                return (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => onSelect(node.id)}
                    className={cn(
                      "group flex w-full max-w-[9.5rem] flex-col items-center text-center",
                      "rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
                    )}
                    aria-pressed={selected}
                  >
                    <span
                      ref={(el) => {
                        anchorRefs.current[node.id] = el;
                      }}
                      className={cn(
                        "pipe-node-core",
                        `pipe-node-${runtime.status}`,
                        column.tint === "blue" &&
                          (runtime.status === "ok" || runtime.status === "started") &&
                          "pipe-node-source",
                        column.tint === "purple" && runtime.status === "ok" && "pipe-node-output",
                        selected && "pipe-node-selected",
                      )}
                    >
                      <span className="pipe-node-ring" />
                      <span className="pipe-node-dot" />
                    </span>
                    <span className="pipe-node-label mt-1.5 font-mono text-[11px] leading-tight">
                      {node.label}
                    </span>
                    <span className="pipe-node-detail mt-0.5 font-mono text-[9px] leading-tight">
                      {node.detail}
                    </span>
                    {runtime.metric ? (
                      <span
                        className={cn(
                          "mt-0.5 font-mono text-[9px] tracking-wide",
                          runtime.status === "refused" || runtime.status === "failed"
                            ? "pipe-metric-fail"
                            : runtime.status === "retry"
                              ? "pipe-metric-retry"
                              : runtime.status === "ok"
                                ? "pipe-metric-ok"
                                : runtime.status === "started"
                                  ? "pipe-metric-active"
                                  : "pipe-metric-muted",
                        )}
                      >
                        {runtime.metric}
                      </span>
                    ) : (
                      <span className="mt-0.5 h-[13px]" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function edgePath(from?: Point, to?: Point): string | null {
  if (!from || !to) return null;
  const midX = (from.x + to.x) / 2;
  return `M ${from.x} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x} ${to.y}`;
}
