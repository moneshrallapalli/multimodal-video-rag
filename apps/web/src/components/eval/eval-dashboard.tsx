"use client";

import { useState } from "react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import data from "@/data/eval-results.json";
import { pct } from "@/lib/format";
import { cn } from "@/lib/utils";

type Config = (typeof data.configs)[number];
type RagasRow = {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
};

const METRICS = [
  { key: "recall_at_5", label: "Recall@5" },
  { key: "recall_at_10", label: "Recall@10" },
  { key: "mrr", label: "MRR" },
  { key: "timestamp_at_5s", label: "Timestamp@5s" },
  { key: "modality_acc", label: "Modality acc" },
] as const;

const ragasByConfig = data.ragas as Record<string, RagasRow | undefined>;

export function EvalDashboard() {
  const [selectedId, setSelectedId] = useState<string>(
    data.configs[data.configs.length - 1].id,
  );
  const selected = data.configs.find((c) => c.id === selectedId) as Config;
  const ragas = ragasByConfig[selectedId];
  const maxR5 = Math.max(...data.configs.map((c) => c.recall_at_5));
  const na = data.no_answer;
  const isSeed = data.meta.status === "real_seed";

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-lg border border-amber-300/60 bg-amber-50 px-4 py-2.5 text-sm text-amber-900">
        <span className="font-medium">{isSeed ? "Seed evaluation." : "Sample data."}</span>{" "}
        {data.meta.note}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-xs font-medium text-muted-foreground">Config:</span>
        {data.configs.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => setSelectedId(c.id)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs transition-colors",
              selectedId === c.id
                ? "border-primary bg-primary/10 font-medium text-primary"
                : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground",
            )}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold">
          Retrieval ablation{" "}
          <span className="font-normal text-muted-foreground">
            · {data.meta.golden_set_size} golden queries · top-{data.meta.retrieval_depth}
          </span>
        </h2>
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Config</TableHead>
                {METRICS.map((m) => (
                  <TableHead key={m.key} className="text-right">
                    {m.label}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.configs.map((c) => (
                <TableRow
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className={cn("cursor-pointer", selectedId === c.id && "bg-primary/5")}
                >
                  <TableCell className="font-medium">{c.label}</TableCell>
                  {METRICS.map((m) => (
                    <TableCell key={m.key} className="text-right tabular-nums">
                      {m.key === "recall_at_5" ? (
                        <div className="flex items-center justify-end gap-2">
                          <div className="hidden h-1.5 w-16 rounded-full bg-muted sm:block">
                            <div
                              className="h-full rounded-full bg-primary"
                              style={{ width: `${(c.recall_at_5 / maxR5) * 100}%` }}
                            />
                          </div>
                          <span>{pct(c[m.key])}</span>
                        </div>
                      ) : (
                        pct(c[m.key])
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-sm font-semibold">RAGAS — {selected.label}</h3>
          {ragas ? (
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              {Object.entries(ragas).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between gap-2">
                  <dt className="text-muted-foreground capitalize">{k.replace(/_/g, " ")}</dt>
                  <dd className="font-medium tabular-nums">{pct(v)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">
              RAGAS / LLM judge metrics were not run for this seed evaluation. Deterministic
              retrieval and no-answer metrics are real.
            </p>
          )}
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-sm font-semibold">No-answer gate</h3>
          <div className="mt-3 grid grid-cols-2 gap-2 text-center">
            <MatrixCell label="True refuse" value={na.true_positive} good />
            <MatrixCell label="Missed refuse" value={na.false_negative} />
            <MatrixCell label="Over-refuse" value={na.false_positive} />
            <MatrixCell label="True answer" value={na.true_negative} good />
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Refusal precision {pct(na.precision)} · recall {pct(na.recall)}
          </p>
        </div>
      </div>
    </div>
  );
}

function MatrixCell({
  label,
  value,
  good,
}: {
  label: string;
  value: number;
  good?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-2",
        good ? "border-primary/30 bg-primary/5" : "border-border bg-muted/40",
      )}
    >
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
