"use client";
import { ArrowRight, FileStack, Info, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/layout/shell";
import { PriorityMark, ReasonChip, RunStatusBadge, StatusBadge, useReasonTitle } from "@/components/status/status";
import { Button } from "@/components/ui/button";
import { Segmented, Tip } from "@/components/ui/overlays";
import { Card, CardHeader, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives";
import { Table, Td, Th, THead, Tr } from "@/components/ui/table";
import { useDashboard, useMe } from "@/lib/api/hooks";
import type { DashboardSummary } from "@/lib/api/types";
import { age, ago, money, ms, pct } from "@/lib/format";
import { cn } from "@/lib/utils";

function Kpi({ label, value, sub, definition, tone, href }: { label: string; value: React.ReactNode;
  sub?: React.ReactNode; definition?: string; tone?: "warning" | "success" | "danger"; href?: string }) {
  const body = (
    <Card className={cn("h-full px-4 py-3.5", href && "transition-colors hover:border-line-strong")}>
      <div className="flex items-center gap-1 text-[12px] text-ink-3">
        <span>{label}</span>
        {definition && (
          <Tip content={definition}><button aria-label={`Definition of ${label}`} onClick={(e) => e.preventDefault()}>
            <Info className="size-3" /></button></Tip>
        )}
      </div>
      <div className={cn("num mt-1 text-[24px] font-semibold tracking-tight", tone === "warning" && "text-warning",
        tone === "danger" && "text-danger", tone === "success" && "text-success")}>{value}</div>
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

export default function OverviewPage() {
  const [days, setDays] = React.useState<"7" | "30" | "90" | "0">("30");
  const { data, error, refetch, isLoading } = useDashboard(Number(days));
  const { data: me } = useMe();
  const router = useRouter();
  const k = data?.kpis;
  const d = data?.definitions ?? {};

  return (
    <div className="mx-auto max-w-[1360px]">
      <PageHeader title="Overview" description="Live figures computed from persisted invoices and runs. Hover the info icons for definitions."
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
            <Kpi label="Received" value={k.received} sub={money(k.total_value, "INR", true)} definition={d.received} href="/invoices" />
            <Kpi label="Ready for approval" value={k.ready_for_approval} sub={`${k.approved} approved`} tone="success"
              href="/review?view=approval" />
            <Kpi label="Needs review" value={k.needs_review} tone={k.needs_review ? "warning" : undefined}
              sub={`${money(k.value_at_risk, "INR", true)} at risk`} definition={d.value_at_risk} href="/review" />
            <Kpi label="On hold" value={k.on_hold} tone={k.on_hold ? "warning" : undefined} href="/review?view=hold" />
            <Kpi label="Rejected" value={k.rejected} tone={k.rejected ? "danger" : undefined}
              sub={`${k.technical_failures} technical failure${k.technical_failures === 1 ? "" : "s"}`} definition={d.technical_failures} />
            <Kpi label="Touchless rate" value={pct(k.touchless_rate)} sub={`of ${k.decided_first_pass} first-pass decisions`}
              definition={d.touchless_rate} />
            <Kpi label="Processing time" value={ms(k.processing_ms_median)} sub={`median · p95 ${ms(k.processing_ms_p95)}`}
              definition={d.processing_time} />
          </div>

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
                  <THead><tr><Th>Invoice</Th><Th>Reason</Th><Th align="right">Amount</Th><Th>Priority</Th><Th align="right">Age</Th></tr></THead>
                  <tbody>
                    {data!.attention.map((i) => (
                      <Tr key={i.id} onClick={() => router.push(`/invoices/${i.id}`)}>
                        <Td><div className="font-medium">{i.reference}</div><div className="max-w-[180px] truncate text-[12px] text-ink-3">{i.vendor?.legal_name ?? i.vendor_name_raw ?? i.original_filename}</div></Td>
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
                <THead><tr><Th>Run</Th><Th>Status</Th><Th>Outcome</Th><Th align="right">Time</Th><Th align="right">Started</Th></tr></THead>
                <tbody>
                  {data!.recent_runs.map((r) => (
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
