"use client";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, FileText, RefreshCw, Radio, ServerCrash } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/shell";
import { ReasonChip, RunStatusBadge, StatusBadge } from "@/components/status/status";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, ErrorState, Kv, Skeleton } from "@/components/ui/primitives";
import { buildStages, RunTimeline } from "@/components/workflow/run-timeline";
import { api, ApiError } from "@/lib/api/client";
import { keys, useInvoice, useMe, useRun } from "@/lib/api/hooks";
import type { Run } from "@/lib/api/types";
import { dateTime, humanize, money, ms, time } from "@/lib/format";
import { useRunStream } from "@/lib/hooks/use-run-stream";
import { cn } from "@/lib/utils";

function Elapsed({ from, to }: { from: string | null; to: string | null }) {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    if (to) return;
    const t = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(t);
  }, [to]);
  if (!from) return <span className="text-ink-3">waiting for worker…</span>;
  const end = to ? new Date(to).getTime() : now;
  return <span className="num">{((end - new Date(from).getTime()) / 1000).toFixed(1)} s</span>;
}

function StreamPill({ state }: { state: string }) {
  const label = { connecting: "Connecting", live: "Live", polling: "Polling (stream unavailable)", ended: "Complete",
    error: "Disconnected" }[state] ?? state;
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11.5px]",
      state === "live" ? "border-accent/30 bg-accent-soft text-accent" : "border-line text-ink-3")}>
      <Radio className={cn("size-3", state === "live" && "lf-pulse")} />{label}
    </span>
  );
}

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { data: me } = useMe();
  const { data: run, error, refetch } = useRun(id);
  const { events, state } = useRunStream(id, () => {
    qc.invalidateQueries({ queryKey: keys.run(id) });
    if (run) qc.invalidateQueries({ queryKey: keys.invoice(run.invoice_id) });
  });
  const { data: invoice } = useInvoice(run?.invoice_id ?? "");
  const [retrying, setRetrying] = React.useState(false);

  const status = events.some((e) => e.event_type === "RUN_FAILED") ? "FAILED"
    : events.some((e) => e.event_type === "RUN_COMPLETED") ? "COMPLETED"
      : events.some((e) => e.event_type === "RUN_STARTED" || e.event_type === "RUN_RESUMED") ? "RUNNING"
        : run?.status ?? "QUEUED";
  React.useEffect(() => { if (status === "COMPLETED" || status === "FAILED") refetch(); }, [status, refetch]);

  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (!run) return <div className="space-y-3"><Skeleton className="h-10 w-80" /><Skeleton className="h-96" /></div>;

  const stages = buildStages(events, run.start_stage, status);
  const startedAt = events.find((e) => e.event_type === "RUN_STARTED" || e.event_type === "RUN_RESUMED")?.occurred_at
    ?? run.started_at;
  const endedAt = [...events].reverse().find((e) => e.event_type === "RUN_COMPLETED" || e.event_type === "RUN_FAILED")
    ?.occurred_at ?? (run.finished_at && status !== "RUNNING" ? run.finished_at : null);
  const prevAttempt = run.attempt > 1 ? run.attempt - 1 : null;
  const done = status === "COMPLETED" || status === "FAILED";

  async function retry() {
    setRetrying(true);
    try {
      const next = await api.post<Run>(`/runs/${id}/retry`);
      toast.success(`Retry started as run #${next.attempt}`);
      router.push(`/runs/${next.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Retry failed");
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div className="mx-auto max-w-[1280px]">
      <PageHeader
        crumbs={[{ href: "/runs", label: "Processing runs" }, { label: `${run.invoice_reference} · run #${run.attempt}` }]}
        title={<span className="flex items-center gap-2.5">Run #{run.attempt} <RunStatusBadge status={status} /></span>}
        description={<span>{run.invoice_filename} · {humanize(run.trigger)} by {run.triggered_by} · {dateTime(run.created_at)}</span>}
        actions={<>
          <StreamPill state={state} />
          <Button asChild variant="secondary"><Link href={`/invoices/${run.invoice_id}`}><FileText />Open investigation</Link></Button>
        </>}
      />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader title="Workflow stages"
            description="Every row is written by the backend as the stage executes; nothing here is simulated."
            action={<span className="text-[12px] text-ink-3">Elapsed <span className="font-medium text-ink"><Elapsed from={startedAt} to={endedAt} /></span></span>} />
          <div className="px-4 pt-4">
            <RunTimeline stages={stages} outputs={run.stage_outputs} previousAttempt={prevAttempt} />
          </div>
        </Card>

        <div className="space-y-5">
          {status === "FAILED" ? (
            <Card className="border-danger/30">
              <div className="flex items-start gap-3 p-4">
                <ServerCrash className="mt-0.5 size-5 text-danger" />
                <div className="min-w-0">
                  <h3 className="text-[14px] font-semibold">Technical failure — not a business decision</h3>
                  <p className="mt-1 text-[12.5px] text-ink-2">{run.error_message ?? "The run failed."}</p>
                  <p className="mt-2 font-mono text-[11.5px] text-ink-3">{run.error_code}</p>
                  <p className="mt-2 text-[12.5px] text-ink-2">
                    {run.retryable ? "This failure is classified as retryable (infrastructure)." :
                      "Not retryable: the same file will fail again. Ask the vendor to re-send a readable PDF."}
                  </p>
                  {run.retryable && me?.role !== "AUDITOR" && (
                    <Button className="mt-3" variant="primary" onClick={retry} loading={retrying}><RefreshCw />Retry run</Button>
                  )}
                </div>
              </div>
            </Card>
          ) : done && invoice ? (
            <Card className="lf-enter">
              <CardHeader title="Decision" action={<StatusBadge status={invoice.status} />} />
              <div className="space-y-3 p-4">
                <p className="text-[13px] leading-relaxed text-ink">{invoice.decision_summary}</p>
                {invoice.reason_codes.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">{invoice.reason_codes.map((c) => <ReasonChip key={c} code={c} />)}</div>
                )}
                {invoice.next_action && (
                  <div className="rounded-md border border-line bg-surface-2 px-3 py-2 text-[12.5px]">
                    <span className="text-ink-3">Next action · </span>{invoice.next_action}
                  </div>
                )}
                <Button asChild variant="primary" className="w-full">
                  <Link href={`/invoices/${invoice.id}`}>Review evidence and checks <ArrowRight /></Link>
                </Button>
              </div>
            </Card>
          ) : (
            <Card>
              <div className="p-4">
                <h3 className="text-[13px] font-semibold">Decision pending</h3>
                <p className="mt-1 text-[12.5px] text-ink-3">The decision is produced by the deterministic decision matrix after every check has run.</p>
              </div>
            </Card>
          )}

          <Card>
            <CardHeader title="Run details" />
            <dl className="grid grid-cols-2 gap-3 p-4">
              <Kv label="Invoice"><Link className="text-accent hover:underline" href={`/invoices/${run.invoice_id}`}>{run.invoice_reference}</Link></Kv>
              <Kv label="Vendor">{run.vendor_name ?? "—"}</Kv>
              <Kv label="Trigger">{humanize(run.trigger)}</Kv>
              <Kv label="Policy">{run.policy_version ? `v${run.policy_version}` : "—"}</Kv>
              <Kv label="Processing time">{ms(run.duration_ms)}</Kv>
              <Kv label="Amount">{invoice ? money(invoice.grand_total, invoice.currency) : "—"}</Kv>
              <Kv label="Extractor" className="col-span-2"><span className="whitespace-normal">{run.extractor ?? "—"}</span></Kv>
              {run.pacing_ms > 0 && <Kv label="Demo pacing" className="col-span-2">
                <span className="text-warning">{run.pacing_ms} ms pause between stages (excluded from durations)</span></Kv>}
            </dl>
          </Card>

          <Card>
            <CardHeader title="Event log" description={`${events.length} persisted event(s), in order`} />
            <ol className="max-h-80 overflow-y-auto px-4 py-2 font-mono text-[11.5px]">
              {events.map((e) => (
                <li key={e.id} className="flex gap-2 border-b border-line py-1 last:border-0">
                  <span className="text-ink-3">{time(e.occurred_at)}</span>
                  <span className={cn("shrink-0", e.status === "FAILURE" ? "text-danger" : e.status === "WARNING" ? "text-warning" : "text-ink-2")}>
                    {e.event_type}</span>
                  <span className="truncate text-ink-3" title={e.message}>{e.stage ?? ""}</span>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>
    </div>
  );
}
