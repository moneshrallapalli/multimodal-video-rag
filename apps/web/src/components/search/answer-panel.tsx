import { Sparkles, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { SearchResponse } from "@/lib/types";

export function AnswerPanel({ response }: { response: SearchResponse }) {
  if (response.refused) {
    return (
      <div className="rounded-xl border border-amber-300/60 bg-amber-50 p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-amber-800">
          <TriangleAlert className="size-4" /> No strong evidence found
        </div>
        <p className="mt-1.5 text-sm text-amber-900/80">{response.answer}</p>
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-border bg-card p-4">
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
    </div>
  );
}
