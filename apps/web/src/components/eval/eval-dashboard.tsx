"use client";

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import { AnimatedNumber } from "@/components/eval/animated-number";
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
import { EASE_OUT_QUINT, expandPanel } from "@/lib/motion";
import { cn } from "@/lib/utils";

type Config = (typeof data.configs)[number];
type RagasRow = {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
};
type JudgeRow = {
  id: string;
  n: number;
  answer_quality: number;
  grounded_rate: number;
  correct_rate: number;
  useful_rate: number;
};
type EvalDataWithJudge = typeof data & {
  judge?: {
    mode: string;
    configs: JudgeRow[];
  };
};

const CORE_METRICS = [
  { key: "mrr", label: "MRR" },
  { key: "timestamp_at_5s", label: "Timestamp@5s" },
  { key: "no_answer_f1", label: "No-answer F1" },
] as const;

const SATURATED_METRICS = [
  { key: "recall_at_5", label: "Recall@5" },
  { key: "recall_at_10", label: "Recall@10" },
  { key: "modality_acc", label: "Modality acc" },
] as const;

type CoreMetricKey = (typeof CORE_METRICS)[number]["key"];
type SaturatedMetricKey = (typeof SATURATED_METRICS)[number]["key"];

const ragasByConfig = data.ragas as Record<string, RagasRow | undefined>;
const judgeByConfig = Object.fromEntries(
  (((data as EvalDataWithJudge).judge?.configs ?? []) as JudgeRow[]).map((row) => [
    row.id,
    row,
  ]),
) as Record<string, JudgeRow | undefined>;

export function EvalDashboard() {
  const [selectedId, setSelectedId] = useState<string>(
    data.configs[data.configs.length - 1].id,
  );
  const [showSaturated, setShowSaturated] = useState(false);
  const selected = data.configs.find((c) => c.id === selectedId) as Config;
  const ragas = ragasByConfig[selectedId];
  const judge = judgeByConfig[selectedId];
  const naByConfig = (data as Record<string, unknown>).no_answer_by_config as
    | Record<string, typeof data.no_answer>
    | undefined;
  const na = naByConfig?.[selectedId] ?? data.no_answer;
  const metaStatus = (data.meta as { status: string }).status;
  const isReal = metaStatus === "real_seed" || metaStatus === "real_expanded";
  const generatedAt = new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/New_York",
  }).format(new Date(data.meta.generated_at));

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-lg border border-amber-300/60 bg-amber-50 px-4 py-2.5 text-sm text-amber-900">
        <p>
          <span className="font-medium">{isReal ? "Real evaluation." : "Sample data."}</span>{" "}
          {data.meta.note}
        </p>
        <dl className="mt-2 grid gap-2 text-xs sm:grid-cols-4">
          <MetaDatum label="Golden set" value="eval/golden/expanded.jsonl" />
          <MetaDatum label="Generated" value={`${generatedAt} ET`} />
          <MetaDatum label="Judge" value={data.meta.judge} />
          <MetaDatum label="Primary config" value={data.meta.primary_config} />
        </dl>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-xs font-medium text-muted-foreground">Config:</span>
        {data.configs.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => setSelectedId(c.id)}
            className={cn(
              "relative rounded-full border px-3 py-1 text-xs transition-colors",
              selectedId === c.id
                ? "border-transparent font-medium text-primary"
                : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground",
            )}
          >
            {/* The pill glides to the selected config (shared layout id). */}
            {selectedId === c.id && (
              <motion.span
                layoutId="config-pill"
                transition={{ duration: 0.3, ease: EASE_OUT_QUINT }}
                className="absolute inset-0 rounded-full border border-primary bg-primary/10"
                aria-hidden
              />
            )}
            <span className="relative">{c.label}</span>
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">
            Retrieval ablation{" "}
            <span className="font-normal text-muted-foreground">
              · {data.meta.golden_set_size} golden queries · top-{data.meta.retrieval_depth}
            </span>
          </h2>
          <button
            type="button"
            onClick={() => setShowSaturated((v) => !v)}
            className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            {showSaturated ? "Hide saturated metrics" : "Show all metrics"}
          </button>
        </div>
        {showSaturated && (
          <p className="text-xs text-muted-foreground">
            Recall and modality accuracy can look similar because top-10 retrieval is generous
            on this focused {data.meta.indexed_video_count}-video corpus. MRR, Timestamp@5s,
            and No-answer F1 are the more useful regression signals here.
          </p>
        )}
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Config</TableHead>
                {CORE_METRICS.map((m) => (
                  <TableHead key={m.key} className="text-right">
                    {m.label}
                  </TableHead>
                ))}
                {showSaturated &&
                  SATURATED_METRICS.map((m) => (
                    <TableHead
                      key={m.key}
                      className="text-right text-muted-foreground"
                    >
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
                  className={cn(
                    "cursor-pointer transition-colors duration-200",
                    selectedId === c.id && "bg-primary/5",
                  )}
                >
                  <TableCell className="font-medium">{c.label}</TableCell>
                  {CORE_METRICS.map((m) => (
                    <TableCell key={m.key} className="text-right tabular-nums">
                      {pct(c[m.key as CoreMetricKey])}
                    </TableCell>
                  ))}
                  {showSaturated &&
                    SATURATED_METRICS.map((m) => (
                      <TableCell
                        key={m.key}
                        className="text-right tabular-nums text-muted-foreground"
                      >
                        {pct(c[m.key as SaturatedMetricKey])}
                      </TableCell>
                    ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      <MetricMethodology selected={selected} na={na} />

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-sm font-semibold">Answer quality — {selected.label}</h3>
          {judge ? (
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <Metric label="Quality" value={judge.answer_quality} />
              <Metric label="Grounded" value={judge.grounded_rate} />
              <Metric label="Correct" value={judge.correct_rate} />
              <Metric label="Useful" value={judge.useful_rate} />
              <div className="col-span-2 mt-1 text-xs text-muted-foreground">
                {judge.n} answerable queries judged by {data.meta.judge}
              </div>
            </dl>
          ) : ragas ? (
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              {Object.entries(ragas).map(([k, v]) => (
                <Metric key={k} label={k.replace(/_/g, " ")} value={v} />
              ))}
            </dl>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">
              LLM judge metrics were not run for this config. Deterministic retrieval and
              no-answer metrics are real.
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
          {na.true_positive + na.false_positive === 0 ? (
            <p className="mt-3 text-xs text-muted-foreground">
              This config never refuses: answer generation is off, and weak-evidence
              refusal lives in the LLM&apos;s grounded flag. All {na.false_negative}{" "}
              expected-refusal queries get answered, so refusal precision and recall
              are undefined (0 refusals attempted) — compare the Production config.
            </p>
          ) : (
            <p className="mt-3 text-xs text-muted-foreground">
              Refusal precision {pct(na.precision)} · recall {pct(na.recall)}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="text-muted-foreground capitalize">{label}</dt>
      <dd className="font-medium tabular-nums">
        <AnimatedNumber value={value} format={pct} />
      </dd>
    </div>
  );
}

function MetaDatum({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-amber-300/60 bg-white/60 px-2 py-1">
      <dt className="text-amber-950/65">{label}</dt>
      <dd className="truncate font-medium">{value}</dd>
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
      <div className="text-lg font-semibold tabular-nums">
        <AnimatedNumber value={value} />
      </div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

function MetricMethodology({
  selected,
  na,
}: {
  selected: Config;
  na: typeof data.no_answer;
}) {
  const [open, setOpen] = useState(false);
  const n = data.meta.golden_set_size;
  const k = data.meta.retrieval_depth;

  return (
    <div className="rounded-xl border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold transition-colors hover:bg-muted/30"
      >
        <span>How metrics are calculated — {selected.label}</span>
        <span
          className={cn(
            "text-xs text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        >
          ▼
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div {...expandPanel} className="overflow-hidden">
            <div className="grid gap-4 border-t border-border px-4 py-4 text-sm md:grid-cols-2">
          <FormulaCard
            title="MRR (Mean Reciprocal Rank)"
            formula="MRR = (1/N) × Σ (1 / rank_i)"
            description={`For each of the ${n} queries, find the rank of the first relevant result. Average the reciprocal ranks. Higher = relevant results appear earlier.`}
            value={selected.mrr}
          />
          <FormulaCard
            title={`Recall@${k}`}
            formula={`R@${k} = queries_with_hit_in_top_${k} / total_queries`}
            description={`Fraction of queries where at least one relevant result appears in the top ${k}. Measures coverage — can we find something?`}
            value={selected.recall_at_5}
          />
          <FormulaCard
            title="Timestamp@5s"
            formula="T@5s = hits_within_5s / total_answerable"
            description="Fraction of answerable queries where the top result's timestamp is within 5 seconds of the ground-truth timestamp. Measures temporal precision."
            value={selected.timestamp_at_5s}
          />
          <FormulaCard
            title="No-answer F1"
            formula="F1 = 2 × (P × R) / (P + R)"
            description={`Precision = ${na.true_positive} / (${na.true_positive} + ${na.false_positive}) = ${pct(na.precision)}. Recall = ${na.true_positive} / (${na.true_positive} + ${na.false_negative}) = ${pct(na.recall)}. Harmonic mean balances over-refusal vs. missed refusal.`}
            value={na.f1}
          />
          <FormulaCard
            title="Modality accuracy"
            formula="Acc = correct_modality / total_answerable"
            description="Fraction of answerable queries where the top result modality (transcript vs. visual) matches the expected modality from the golden set."
            value={selected.modality_acc}
          />
              <FormulaCard
                title="Config features"
                formula=""
                description={`Hybrid BM25: ${selected.enable_hybrid_transcript ? "on" : "off"} · Cross-encoder rerank: ${selected.enable_cross_encoder_rerank ? "on" : "off"} · Query rewrite: ${selected.enable_query_rewrite ? "on" : "off"} · Answer generation: ${selected.enable_answer_generation ? "on" : "off"}`}
                value={null}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function FormulaCard({
  title,
  formula,
  description,
  value,
}: {
  title: string;
  formula: string;
  description: string;
  value: number | null;
}) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 p-3">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold">{title}</h4>
        {value !== null && (
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-bold tabular-nums text-primary">
            {pct(value)}
          </span>
        )}
      </div>
      {formula && (
        <code className="mt-1.5 block rounded bg-muted px-2 py-1 font-mono text-xs">
          {formula}
        </code>
      )}
      <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{description}</p>
    </div>
  );
}
