"use client";
import { Cpu, Download, History, Search, User as UserIcon } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { PageHeader } from "@/components/layout/shell";
import { Badge, ReasonChip } from "@/components/status/status";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/overlays";
import { Card, EmptyState, ErrorState, Input, Select } from "@/components/ui/primitives";
import { Pagination, SkeletonRows, Table, Td, Th, THead, Tr } from "@/components/ui/table";
import { qs } from "@/lib/api/client";
import { useAudit, useAuditActions } from "@/lib/api/hooks";
import type { AuditEvent } from "@/lib/api/types";
import { dateTime, humanize } from "@/lib/format";

type Actor = "ALL" | "SYSTEM" | "USER";

function useDebounced<T>(value: T, delay = 300): T {
  const [v, setV] = React.useState(value);
  React.useEffect(() => {
    const t = setTimeout(() => setV(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return v;
}

function show(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return v.length ? v.map(show).join(", ") : "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function ChangeSummary({ e }: { e: AuditEvent }) {
  const before = e.before ?? {};
  const after = e.after ?? {};
  const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).slice(0, 4);
  if (!keys.length) return <span className="text-ink-3">—</span>;
  return (
    <ul className="space-y-0.5">
      {keys.map((k) => {
        const inB = k in before;
        const inA = k in after;
        return (
          <li key={k} className="truncate text-[12px]" title={`${k}: ${inB ? show(before[k]) + " → " : ""}${show(after[k])}`}>
            <span className="text-ink-3">{humanize(k)}:</span>{" "}
            {inB && inA ? (
              <><span className="text-ink-2">{show(before[k])}</span> <span className="text-ink-3">→</span>{" "}
                <span className="text-ink">{show(after[k])}</span></>
            ) : <span className="text-ink-2">{show(inA ? after[k] : before[k])}</span>}
          </li>
        );
      })}
    </ul>
  );
}

export default function AuditPage() {
  const [search, setSearch] = React.useState("");
  const q = useDebounced(search);
  const [actor, setActor] = React.useState<Actor>("ALL");
  const [action, setAction] = React.useState("");
  const [page, setPage] = React.useState(1);
  React.useEffect(() => setPage(1), [q, actor, action]);

  const filters = { q: q || undefined, actor_type: actor === "ALL" ? undefined : actor, action: action || undefined };
  const { data, isLoading, isError, error, refetch } = useAudit({ ...filters, page });
  const { data: actions } = useAuditActions();

  return (
    <div>
      <PageHeader title="Audit log"
        description="Immutable, append-only record of every system and human action. The database rejects updates and deletes on this table."
        actions={
          <Button asChild variant="secondary">
            <a href={`/api/audit/export.csv${qs(filters)}`} download><Download />Export CSV</a>
          </Button>
        } />
      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2.5">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-3" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search entity, actor, note…"
              className="pl-8" aria-label="Search audit log" />
          </div>
          <Segmented<Actor> value={actor} onChange={setActor}
            options={[{ value: "ALL", label: "All" }, { value: "SYSTEM", label: "System" }, { value: "USER", label: "Human" }]} />
          <Select value={action} onChange={(e) => setAction(e.target.value)} aria-label="Filter by action">
            <option value="">All actions</option>
            {(actions ?? []).map((a) => <option key={a} value={a}>{humanize(a)}</option>)}
          </Select>
        </div>
        {isError ? (
          <div className="p-3"><ErrorState error={error} onRetry={() => refetch()} /></div>
        ) : (
          <>
            <Table>
              <THead>
                <tr>
                  <Th>Time</Th><Th>Actor</Th><Th>Action</Th><Th>Entity</Th><Th>Reason</Th><Th>Note</Th>
                  <Th>Change</Th>
                </tr>
              </THead>
              <tbody>
                {isLoading ? <SkeletonRows rows={10} cols={7} /> : (data?.items ?? []).map((e) => (
                  <Tr key={e.id}>
                    <Td className="whitespace-nowrap font-mono text-[11.5px] text-ink-2">{dateTime(e.occurred_at)}</Td>
                    <Td>
                      <div className="flex items-center gap-2">
                        {e.actor_type === "SYSTEM"
                          ? <Badge tone="neutral" icon={<Cpu />}>System</Badge>
                          : <Badge tone="accent" icon={<UserIcon />}>Human</Badge>}
                        <span className="max-w-[180px] truncate text-[12.5px] text-ink-2" title={e.actor_name}>{e.actor_name}</span>
                      </div>
                    </Td>
                    <Td className="whitespace-nowrap font-medium">{humanize(e.action)}</Td>
                    <Td className="whitespace-nowrap">
                      {e.invoice_id ? (
                        <Link href={`/invoices/${e.invoice_id}`} className="text-accent hover:underline">
                          {e.entity_label ?? "Invoice"}
                        </Link>
                      ) : <span className="text-ink-2">{e.entity_label ?? humanize(e.entity_type)}</span>}
                    </Td>
                    <Td>{e.reason_code ? <ReasonChip code={e.reason_code} /> : <span className="text-ink-3">—</span>}</Td>
                    <Td className="max-w-[260px]">
                      <span className="block truncate text-[12.5px] text-ink-2" title={e.note ?? undefined}>{e.note ?? "—"}</span>
                    </Td>
                    <Td className="max-w-[300px]"><ChangeSummary e={e} /></Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
            {!isLoading && data && data.items.length === 0 && (
              <EmptyState icon={<History />} title="No audit events match"
                description="Try clearing the search or filters. Every upload, decision and review action is recorded here." />
            )}
            {data && data.total > 0 && (
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            )}
          </>
        )}
      </Card>
    </div>
  );
}
