"use client";

import {
  PIPELINE_COLUMNS,
  PIPELINE_EDGES,
  isRetryLive,
  type DisplayNodeId,
  type NodeRuntimeState,
} from "@/lib/pipeline";

import { CockpitGraph } from "./cockpit-graph";

export function PipelineGraph({
  nodes,
  selectedId,
  onSelect,
  reduceMotion,
}: {
  nodes: Record<DisplayNodeId, NodeRuntimeState>;
  selectedId: DisplayNodeId | null;
  onSelect: (id: DisplayNodeId) => void;
  reduceMotion: boolean;
}) {
  const retryLive = isRetryLive(nodes);
  return (
    <CockpitGraph
      columns={PIPELINE_COLUMNS}
      edges={PIPELINE_EDGES}
      nodes={nodes}
      selectedId={selectedId}
      onSelect={onSelect}
      reduceMotion={reduceMotion}
      dimColumn={(columnId) => columnId === "retry" && !retryLive}
      isLiveEdge={(from, to) => {
        if (from === "retrieve_again" && !retryLive) return false;
        if (to === "rewrite_query" && nodes.rewrite_query.status === "skipped") return false;
        return nodes[from].status !== "idle" && nodes[to].status !== "idle";
      }}
    />
  );
}
