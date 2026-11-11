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
