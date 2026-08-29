"use client";

import { Sparkles, TriangleAlert } from "lucide-react";
import { motion } from "motion/react";

import { Badge } from "@/components/ui/badge";
import { revealItem } from "@/lib/motion";
import type { SearchResponse } from "@/lib/types";

export function AnswerPanel({ response }: { response: SearchResponse }) {
  if (response.refused) {
    const backendFailed = response.refusal_reason === "pipeline_error";
    return (
      <motion.div
        variants={revealItem}
        className={
          backendFailed
            ? "rounded-2xl border border-destructive/25 bg-destructive/5 p-4 shadow-sm"
            : "rounded-2xl border border-primary/20 bg-primary/5 p-4 shadow-sm"
        }
      >
        <div
          className={
            backendFailed
              ? "flex items-center gap-2 text-sm font-medium text-destructive"
              : "flex items-center gap-2 text-sm font-medium text-primary"
          }
        >
          <TriangleAlert className="size-4" />
          {backendFailed ? "Search backend failed" : "No strong evidence found"}
        </div>
        <p className="mt-1.5 text-sm text-muted-foreground">{response.answer}</p>
      </motion.div>
    );
  }
  return (
    <motion.div
      variants={revealItem}
      className="rounded-2xl border border-border bg-card p-4 shadow-sm"
    >
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-primary" />
        <span className="text-sm font-semibold">Answer</span>
        <Badge variant="secondary" className="ml-auto">
          Grounded answer
        </Badge>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-foreground/90">{response.answer}</p>
      <p className="mt-2 text-xs text-muted-foreground">
        Grounded in {response.results.length} moment
        {response.results.length === 1 ? "" : "s"} · intent: {response.intent}
      </p>
    </motion.div>
  );
}
