"use client";
import { AlertTriangle, ArrowRight, Ban, CheckCircle2, Clock, Cpu, FileStack, Gauge, Inbox, Info, ServerCrash, ShieldCheck,
  Timer, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/layout/shell";
import { PriorityMark, ReasonChip, RunStatusBadge, StatusBadge, useReasonTitle } from "@/components/status/status";
import { Button } from "@/components/ui/button";
import { Segmented, Tip } from "@/components/ui/overlays";
import { Avatar, Card, CardHeader, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives";
import { SortTh, Table, Td, THead, Tr, useClientSort } from "@/components/ui/table";
import { useDashboard, useMe } from "@/lib/api/hooks";
import type { DashboardSummary } from "@/lib/api/types";
import { age, ago, money, ms, pct, STAGES } from "@/lib/format";
import { cn } from "@/lib/utils";

const ICON_TONE = { success: "bg-success-soft text-success", warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger", accent: "bg-accent-soft text-accent", neutral: "bg-surface-3 text-ink-2" };

function Kpi({ label, value, sub, definition, tone, href, icon }: { label: string; value: React.ReactNode;
  sub?: React.ReactNode; definition?: string; tone?: "warning" | "success" | "danger"; href?: string;
  icon?: React.ReactNode }) {
  const body = (
    <Card className={cn("h-full p-4", href && "transition-all hover:-translate-y-0.5 hover:shadow-pop")}>
      {icon && <span className={cn("mb-3 inline-flex size-9 items-center justify-center rounded-xl [&_svg]:size-[18px]",
        ICON_TONE[tone ?? "accent"])}>{icon}</span>}
      <div className="flex items-center gap-1 text-[12.5px] text-ink-3">
        <span>{label}</span>
        {definition && (
          <Tip content={definition}><button aria-label={`Definition of ${label}`} onClick={(e) => e.preventDefault()}>
            <Info className="size-3" /></button></Tip>
        )}
      </div>
      <div className="num mt-0.5 text-[26px] font-semibold tracking-tight text-ink">{value}</div>
      {sub && <div className="num mt-0.5 text-[12px] text-ink-3">{sub}</div>}
    </Card>
  );
  return href ? <Link href={href} className="block">{body}</Link> : body;
}

function VolumeChart({ data }: { data: DashboardSummary["series"] }) {
  const rows = data.map((d) => ({ ...d, label: d.date.slice(5), other: Math.max(0, d.received - d.ready_or_approved - d.exceptions) }));
  return (
    <div>
      <div className="mb-2 flex items-center gap-4 px-1 text-[12px] text-ink-2" aria-label="Legend">
        <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: "var(--chart-ok)" }} />Ready or approved</span>
        <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: "var(--chart-exception)" }} />Exceptions (review, hold, rejected)</span>
      </div>
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 4, left: -18, bottom: 0 }} barCategoryGap="22%" maxBarSize={28}>
            <CartesianGrid vertical={false} stroke="var(--line)" />
            <XAxis dataKey="label" minTickGap={24} tickLine={false} axisLine={{ stroke: "var(--line-strong)" }} tick={{ fill: "var(--ink-3)", fontSize: 11 }} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "var(--ink-3)", fontSize: 11 }} />
            <Tooltip cursor={{ fill: "var(--surface-3)" }} content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as (typeof rows)[number];
              return (
                <div className="rounded-md border border-line bg-surface px-3 py-2 text-[12px] shadow-lg">
                  <div className="mb-1 font-medium text-ink">{label}</div>
                  <div className="num text-ink-2">Received {p.received} · {money(p.value, "INR", true)}</div>
                  <div className="num text-ink-2">Ready/approved {p.ready_or_approved}</div>
                  <div className="num text-ink-2">Exceptions {p.exceptions}</div>
                </div>
              );
            }} />
            <Bar dataKey="ready_or_approved" stackId="a" fill="var(--chart-ok)" stroke="var(--surface)" strokeWidth={2} />
            <Bar dataKey="exceptions" stackId="a" fill="var(--chart-exception)" stroke="var(--surface)" strokeWidth={2} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Breakdown({ items }: { items: DashboardSummary["exception_breakdown"] }) {
  const title = useReasonTitle();
  const max = Math.max(1, ...items.map((i) => i.count));
  return (
    <ul className="space-y-2.5">
      {items.map((i) => (
        <li key={i.code}>
          <div className="mb-1 flex items-center justify-between text-[12.5px]">
            <span className="truncate text-ink-2" title={i.code}>{title(i.code)}</span>
            <span className="num font-medium text-ink">{i.count}</span>
          </div>
          <div className="h-1.5 rounded-full bg-surface-3">
            <div className="h-1.5 rounded-full bg-accent" style={{ width: `${(i.count / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

const OUTCOMES = [
  { key: "READY_FOR_APPROVAL", label: "Ready for approval", hint: "All checks passed; awaits a second person",
    icon: <CheckCircle2 />, tone: "success" as const },
  { key: "APPROVED", label: "Approved", hint: "Authorised for the payment run", icon: <ShieldCheck />, tone: "accent" as const },
  { key: "NEEDS_REVIEW", label: "Needs review", hint: "A person resolves the exception", icon: <AlertTriangle />, tone: "warning" as const },
  { key: "ON_HOLD", label: "On hold", hint: "Waiting on receipt, onboarding or vendor", icon: <Clock />, tone: "warning" as const },
  { key: "REJECTED", label: "Rejected", hint: "Defined policy violation", icon: <Ban />, tone: "danger" as const },
  { key: "FAILED", label: "Technical failure", hint: "Unreadable file; never a rejection", icon: <ServerCrash />, tone: "neutral" as const },
];

function FlowMap({ data }: { data: DashboardSummary }) {
  const router = useRouter();
  const [stage, setStage] = React.useState(STAGES[4].key);
  const k = data.kpis;
  const live = k.processing > 0 || data.queue.running > 0;
  const active = STAGES.find((s) => s.key === stage)!;
  return (
    <Card className="mt-5 overflow-hidden">
      <CardHeader title="How invoices flow through LedgerFlow"
        description="Live counts for the selected period. Click a stage to see what it does, or an outcome to open those invoices." />
      <div className="grid gap-5 p-5 lg:grid-cols-[170px_minmax(0,1fr)_minmax(250px,320px)] lg:items-center">
        <button onClick={() => router.push("/invoices")}
          className="group rounded-2xl border border-line bg-surface-2 p-4 text-left transition-all hover:border-line-strong hover:shadow-card">
          <span className="inline-flex size-9 items-center justify-center rounded-xl bg-accent-soft text-accent"><Inbox className="size-[18px]" /></span>
          <div className="mt-3 text-[12.5px] text-ink-3">PDFs received</div>
          <div className="num text-[26px] font-semibold">{k.received}</div>
          <div className="text-[12px] text-ink-3">{money(k.total_value, "INR", true)} total</div>
        </button>

        <div className="relative">
          <div className="mb-3 flex items-center gap-2">
            <span className={cn("h-[3px] flex-1 rounded-full", live ? "lf-flow" : "bg-line-strong")} />
            <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-[12px] text-ink-2">
              <Cpu className="size-3.5 text-accent" />{live ? `${k.processing || data.queue.running} processing now` : "Automated pipeline"}
            </span>
            <span className={cn("h-[3px] flex-1 rounded-full", live ? "lf-flow" : "bg-line-strong")} />
          </div>
          <ol className="grid grid-cols-5 gap-1.5 sm:grid-cols-10">
            {STAGES.map((s, i) => (
              <li key={s.key}>
                <button onClick={() => setStage(s.key)} onMouseEnter={() => setStage(s.key)} aria-pressed={stage === s.key}
                  className={cn("flex w-full flex-col items-center gap-1.5 rounded-xl px-1 py-2 text-center transition-all",
                    stage === s.key ? "bg-accent-soft" : "hover:bg-surface-3")}>
                  <span className={cn("flex size-7 items-center justify-center rounded-full text-[11.5px] font-semibold",
                    stage === s.key ? "bg-accent text-accent-ink" : "bg-surface-3 text-ink-2")}>{i + 1}</span>
                  <span className="text-[10.5px] leading-tight text-ink-2">{s.label}</span>
                </button>
              </li>
            ))}
          </ol>
          <div className="mt-3 rounded-xl border border-line bg-surface-2 px-4 py-3 text-[12.5px]">
            <span className="font-medium text-ink">{active.label}.</span> <span className="text-ink-2">{active.description}.</span>
            <span className="text-ink-3"> Every stage writes an event and its checks before the next one starts.</span>
          </div>
        </div>

        <ul className="space-y-1.5">
          {OUTCOMES.map((o) => {
            const n = data.status_counts[o.key] ?? 0;
            return (
              <li key={o.key}>
                <button onClick={() => router.push(`/invoices?status=${o.key}`)}
                  className="group flex w-full items-center gap-3 rounded-xl border border-transparent px-3 py-2 text-left transition-all hover:border-line hover:bg-surface-2">
                  <span className={cn("inline-flex size-8 items-center justify-center rounded-lg [&_svg]:size-4", ICON_TONE[o.tone])}>{o.icon}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13px] font-medium text-ink">{o.label}</span>
                    <span className="block truncate text-[11.5px] text-ink-3">{o.hint}</span>
                  </span>
                  <span className="text-right">
                    <span className="num block text-[15px] font-semibold">{n}</span>
                    <span className="num block text-[11px] text-ink-3">{money(data.status_value[o.key] ?? "0", "INR", true)}</span>
                  </span>
                  <ArrowRight className="size-3.5 text-ink-3 opacity-0 transition-opacity group-hover:opacity-100" />
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </Card>
  );
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export default function OverviewPage() {
  const [days, setDays] = React.useState<"7" | "30" | "90" | "0">("30");
  const { data, error, refetch, isLoading } = useDashboard(Number(days));
  const { data: me } = useMe();
  const router = useRouter();
  const k = data?.kpis;
  const d = data?.definitions ?? {};
  const att = useClientSort(data?.attention, {
    invoice: (i) => i.reference, reason: (i) => i.reason_codes[0] ?? "", amount: (i) => Number(i.grand_total ?? 0),
    priority: (i) => ({ HIGH: 0, NORMAL: 1, LOW: 2 } as Record<string, number>)[i.priority] ?? 3, age: (i) => i.age_hours ?? 0,
  }, { sort: "priority", order: "asc" });
  const rr = useClientSort(data?.recent_runs, {
    run: (r) => r.invoice_reference, status: (r) => r.status, outcome: (r) => r.decision ?? r.error_code ?? "",
    time: (r) => r.duration_ms ?? 0, started: (r) => r.created_at,
  }, { sort: "started", order: "desc" });

  return (
    <div className="mx-auto max-w-[1360px]">
      <PageHeader title={`${greeting()}${me ? `, ${me.name.split(" ")[0]}` : ""}`}
        description={k ? `${k.needs_review + k.on_hold} invoice${k.needs_review + k.on_hold === 1 ? "" : "s"} need a person and ${k.ready_for_approval} ${k.ready_for_approval === 1 ? "is" : "are"} ready for approval. All figures are computed live from processed runs.` : "Loading your workspace…"}
        actions={<Segmented value={days} onChange={setDays} options={[{ value: "7", label: "7 days" },
          { value: "30", label: "30 days" }, { value: "90", label: "90 days" }, { value: "0", label: "All time" }]} />} />
      {error && <ErrorState error={error} onRetry={() => refetch()} />}
      {isLoading || !k ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">{Array.from({ length: 7 }).map((_, i) => <Skeleton key={i} className="h-[92px]" />)}</div>
      ) : k.received === 0 && data!.recent_runs.length === 0 ? (
        <Card>
          <EmptyState icon={<FileStack />} title="No invoices yet"
            description="Upload a PDF to start the first processing run. Every figure on this page is computed from real runs; nothing is pre-filled."
            action={me?.role !== "AUDITOR" && <Button asChild variant="primary"><Link href="/invoices/new"><Upload />Upload invoices</Link></Button>} />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <Kpi icon={<FileStack />} label="Received" value={k.received} sub={money(k.total_value, "INR", true)} definition={d.received} href="/invoices" />
            <Kpi icon={<CheckCircle2 />} label="Ready for approval" value={k.ready_for_approval} sub={`${k.approved} approved`} tone="success"
              href="/review?view=approval" />
            <Kpi icon={<AlertTriangle />} label="Needs review" value={k.needs_review} tone="warning"
              sub={`${money(k.value_at_risk, "INR", true)} at risk`} definition={d.value_at_risk} href="/review" />
            <Kpi icon={<Clock />} label="On hold" value={k.on_hold} tone="warning" href="/review?view=hold" />
            <Kpi icon={<Ban />} label="Rejected" value={k.rejected} tone="danger"
              sub={`${k.technical_failures} technical failure${k.technical_failures === 1 ? "" : "s"}`} definition={d.technical_failures} />
            <Kpi icon={<Gauge />} label="Touchless rate" value={pct(k.touchless_rate)} sub={`of ${k.decided_first_pass} first-pass decisions`}
              definition={d.touchless_rate} />
            <Kpi icon={<Timer />} label="Processing time" value={ms(k.processing_ms_median)} sub={`median · p95 ${ms(k.processing_ms_p95)}`}
              definition={d.processing_time} />
          </div>

          <FlowMap data={data!} />

          <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
            <Card>
              <CardHeader title="Daily intake and first outcome" description="Invoices received per day, split by current outcome" />
              <div className="p-4">{data!.series.length ? <VolumeChart data={data!.series} /> :
                <p className="py-10 text-center text-[13px] text-ink-3">No invoices in this period.</p>}</div>
            </Card>
            <Card>
              <CardHeader title="Exception breakdown" description="Top reasons on invoices currently in review, hold or rejected" />
              <div className="p-4">{data!.exception_breakdown.length ? <Breakdown items={data!.exception_breakdown} /> :
                <p className="py-10 text-center text-[13px] text-ink-3">No open exceptions.</p>}</div>
            </Card>
          </div>

          <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <Card>
              <CardHeader title="Needs attention" description="High priority first, then oldest"
                action={<Button asChild size="sm" variant="ghost"><Link href="/review">Review queue <ArrowRight /></Link></Button>} />
              {data!.attention.length === 0 ? <p className="px-4 py-8 text-center text-[13px] text-ink-3">Queue is clear.</p> : (
                <Table>
                  <THead><tr><SortTh label="Invoice" field="invoice" sort={att.sort} order={att.order} onSort={att.onSort} />
                    <SortTh label="Reason" field="reason" sort={att.sort} order={att.order} onSort={att.onSort} />
                    <SortTh label="Amount" field="amount" align="right" sort={att.sort} order={att.order} onSort={att.onSort} />
                    <SortTh label="Priority" field="priority" sort={att.sort} order={att.order} onSort={att.onSort} />
                    <SortTh label="Age" field="age" align="right" sort={att.sort} order={att.order} onSort={att.onSort} /></tr></THead>
                  <tbody>
                    {(att.rows ?? []).map((i) => (
                      <Tr key={i.id} onClick={() => router.push(`/invoices/${i.id}`)}>
                        <Td><div className="flex items-center gap-2.5"><Avatar name={i.vendor?.legal_name ?? i.vendor_name_raw ?? "?"} />
                          <div className="min-w-0"><div className="font-medium">{i.reference}</div><div className="max-w-[170px] truncate text-[12px] text-ink-3">{i.vendor?.legal_name ?? i.vendor_name_raw ?? i.original_filename}</div></div></div></Td>
                        <Td>{i.reason_codes[0] ? <ReasonChip code={i.reason_codes[0]} /> : <StatusBadge status={i.status} />}</Td>
                        <Td align="right">{money(i.grand_total, i.currency)}</Td>
                        <Td><PriorityMark priority={i.priority} /></Td>
                        <Td align="right">{age(i.age_hours)}</Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card>
            <Card>
              <CardHeader title="Recent runs" description={`${data!.queue.queued} queued · ${data!.queue.running} running`}
                action={<Button asChild size="sm" variant="ghost"><Link href="/runs">All runs <ArrowRight /></Link></Button>} />
              <Table>
                <THead><tr><SortTh label="Run" field="run" sort={rr.sort} order={rr.order} onSort={rr.onSort} />
                  <SortTh label="Status" field="status" sort={rr.sort} order={rr.order} onSort={rr.onSort} />
                  <SortTh label="Outcome" field="outcome" sort={rr.sort} order={rr.order} onSort={rr.onSort} />
                  <SortTh label="Time" field="time" align="right" sort={rr.sort} order={rr.order} onSort={rr.onSort} />
                  <SortTh label="Started" field="started" align="right" sort={rr.sort} order={rr.order} onSort={rr.onSort} /></tr></THead>
                <tbody>
                  {(rr.rows ?? []).map((r) => (
                    <Tr key={r.id} onClick={() => router.push(`/runs/${r.id}`)}>
                      <Td><div className="font-medium">{r.invoice_reference} <span className="text-ink-3">#{r.attempt}</span></div>
                        <div className="max-w-[200px] truncate text-[12px] text-ink-3">{r.vendor_name ?? r.invoice_filename}</div></Td>
                      <Td><RunStatusBadge status={r.status} /></Td>
                      <Td>{r.decision ? <StatusBadge status={r.decision} /> : r.error_code ? <span className="font-mono text-[11.5px] text-danger">{r.error_code}</span> : "—"}</Td>
                      <Td align="right">{ms(r.duration_ms)}</Td>
                      <Td align="right" className="text-[12px] text-ink-3">{ago(r.created_at)}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
