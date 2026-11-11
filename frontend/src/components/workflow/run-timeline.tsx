"use client";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Circle, CornerDownRight, Loader2, XCircle } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/status/status";
import type { RunEvent } from "@/lib/api/types";
import { ms, STAGES, time } from "@/lib/format";
import { cn } from "@/lib/utils";

export type StageView = {
  key: string; label: string; description: string;
  state: "pending" | "running" | "success" | "warning" | "failed" | "reused";
  started?: RunEvent; finished?: RunEvent;
};

export function buildStages(events: RunEvent[], startStage: string, runStatus: string): StageView[] {
  const startIdx = STAGES.findIndex((s) => s.key === startStage);
  return STAGES.map((s, i) => {
    const started = events.find((e) => e.stage === s.key && e.event_type === "STAGE_STARTED");
    const finished = [...events].reverse().find((e) => e.stage === s.key &&
      (e.event_type === "STAGE_COMPLETED" || e.event_type === "STAGE_FAILED"));
    let state: StageView["state"] = "pending";
    if (s.key !== "RECEIVED" && startIdx > 0 && i < startIdx) state = "reused";
    if (finished) state = finished.event_type === "STAGE_FAILED" ? "failed" : finished.status === "WARNING" ? "warning" : "success";
    else if (started) state = runStatus === "FAILED" ? "failed" : "running";
    return { ...s, state, started, finished };
  });
}

const ICON = {
  pending: <Circle className="size-[18px] text-line-strong" />,
  running: <Loader2 className="size-[18px] animate-spin text-accent" />,
  success: <CheckCircle2 className="size-[18px] text-success" />,
  warning: <AlertTriangle className="size-[18px] text-warning" />,
  failed: <XCircle className="size-[18px] text-danger" />,
  reused: <CornerDownRight className="size-[18px] text-ink-3" />,
};

function Details({ value }: { value: unknown }) {
  return (
    <pre className="mt-2 max-h-72 overflow-auto rounded-md border border-line bg-surface-2 p-2.5 font-mono text-[11.5px] leading-relaxed text-ink-2">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

export function RunTimeline({ stages, outputs, previousAttempt }: { stages: StageView[];
  outputs?: Record<string, unknown>; previousAttempt?: number | null }) {
  const [open, setOpen] = React.useState<Record<string, boolean>>({});
  return (
    <ol className="relative">
      {stages.map((s, i) => {
        const failedChecks = (s.finished?.details as { checks_failed?: string[] } | null)?.checks_failed ?? [];
        const passed = (s.finished?.details as { checks_passed?: number } | null)?.checks_passed;
        const expandable = !!(s.finished && (outputs?.[s.key] || s.finished.details));
        return (
          <li key={s.key} className={cn("relative flex gap-3 pb-4", s.state === "running" && "lf-enter")}>
            {i < stages.length - 1 && (
              <span aria-hidden className={cn("absolute left-[8.5px] top-6 bottom-0 w-px",
                ["success", "warning", "reused"].includes(s.state) ? "bg-line-strong" : "bg-line")} />
            )}
            <span className="relative z-10 mt-0.5 bg-surface">{ICON[s.state]}</span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className={cn("text-[13px] font-medium", s.state === "pending" ? "text-ink-3" : "text-ink")}>{s.label}</span>
                {s.state === "running" && <span className="text-[12px] text-accent">running…</span>}
                {s.state === "reused" && <span className="text-[12px] text-ink-3">reused from run #{previousAttempt ?? "previous"} (extraction is not repeated on re-evaluation)</span>}
                {s.finished?.duration_ms !== undefined && s.finished?.duration_ms !== null && (
                  <span className="num rounded bg-surface-3 px-1.5 text-[11.5px] text-ink-2">{ms(s.finished.duration_ms)}</span>
                )}
                {passed !== undefined && passed > 0 && <span className="text-[11.5px] text-ink-3">{passed} check{passed === 1 ? "" : "s"} passed</span>}
                {failedChecks.map((c) => <Badge key={c} tone="warning" className="h-5 text-[11px]">{c}</Badge>)}
                {s.finished && <span className="ml-auto font-mono text-[11px] text-ink-3">{time(s.finished.occurred_at)}</span>}
              </div>
              <p className={cn("mt-0.5 text-[12.5px]", s.state === "failed" ? "text-danger" : "text-ink-2")}>
                {s.finished?.message ?? (s.state === "pending" ? s.description : s.started ? "In progress" : s.description)}
              </p>
              {s.finished?.evidence_refs && s.finished.evidence_refs.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {s.finished.evidence_refs.map((r) => <span key={r} className="rounded border border-line px-1.5 font-mono text-[11px] text-ink-3">{r}</span>)}
                </div>
              )}
              {expandable && (
                <button onClick={() => setOpen((o) => ({ ...o, [s.key]: !o[s.key] }))}
                  className="mt-1 inline-flex items-center gap-1 text-[12px] text-ink-3 hover:text-ink" aria-expanded={!!open[s.key]}>
                  {open[s.key] ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                  Structured output
                </button>
              )}
              {open[s.key] && <Details value={outputs?.[s.key] ?? s.finished?.details} />}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function RunStepper({ stages, status }: { stages: StageView[]; status: string }) {
  const done = stages.filter((s) => ["success", "warning", "reused", "failed"].includes(s.state)).length;
  const pctDone = Math.round((done / stages.length) * 100);
  const current = stages.find((s) => s.state === "running");
  const failed = stages.find((s) => s.state === "failed");
  return (
    <div className="px-5 pb-1 pt-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <div className="text-[13px] text-ink-2">
          {failed ? <span className="font-medium text-danger">Stopped at {failed.label}</span>
            : status === "COMPLETED" ? <span className="font-medium text-success">All stages complete</span>
              : current ? <>Now running <span className="font-medium text-ink">{current.label}</span></>
                : <span className="text-ink-3">Waiting for a worker to pick up the job…</span>}
        </div>
        <span className="num text-[12.5px] font-medium text-ink-2">{pctDone}%</span>
      </div>
      <div className="relative h-2 overflow-hidden rounded-full bg-surface-3">
        <div className={cn("absolute inset-y-0 left-0 rounded-full transition-[width] duration-500 ease-out",
          failed ? "bg-danger" : status === "COMPLETED" ? "bg-success" : "bg-accent")} style={{ width: `${pctDone}%` }} />
        {status !== "COMPLETED" && !failed && <div className="lf-flow absolute inset-y-0 opacity-30" style={{ left: `${pctDone}%`, right: 0 }} />}
      </div>
      <ol className="mt-4 hidden grid-cols-10 gap-1 md:grid">
        {stages.map((s) => (
          <li key={s.key} className="flex flex-col items-center gap-1.5 text-center">
            <span className={cn("flex size-7 items-center justify-center rounded-full border-2 bg-surface transition-all",
              s.state === "success" && "border-success bg-success-soft text-success",
              s.state === "warning" && "border-warning bg-warning-soft text-warning",
              s.state === "failed" && "border-danger bg-danger-soft text-danger",
              s.state === "running" && "lf-ring border-accent text-accent",
              s.state === "reused" && "border-line-strong text-ink-3",
              s.state === "pending" && "border-line text-line-strong")}>
              {s.state === "success" ? <CheckCircle2 className="size-4" /> : s.state === "warning" ? <AlertTriangle className="size-3.5" />
                : s.state === "failed" ? <XCircle className="size-4" /> : s.state === "running" ? <Loader2 className="size-3.5 animate-spin" />
                  : s.state === "reused" ? <CornerDownRight className="size-3.5" /> : <Circle className="size-2.5 fill-current" />}
            </span>
            <span className={cn("text-[10.5px] leading-tight", s.state === "pending" ? "text-ink-3" : "text-ink-2",
              s.state === "running" && "font-medium text-accent")}>{s.label}</span>
            {s.finished?.duration_ms !== undefined && s.finished?.duration_ms !== null &&
              <span className="num text-[10px] text-ink-3">{ms(s.finished.duration_ms)}</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}
