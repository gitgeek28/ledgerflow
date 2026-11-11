"use client";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCheck, Inbox } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/shell";
import { PriorityMark, ReasonChip, StatusBadge } from "@/components/status/status";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/overlays";
import { Avatar, Card, EmptyState, ErrorState } from "@/components/ui/primitives";
import { SkeletonRows, SortTh, Table, Td, Th, THead, Tr, useClientSort } from "@/components/ui/table";
import { api } from "@/lib/api/client";
import { useMe, useReviewQueue } from "@/lib/api/hooks";
import { age, money } from "@/lib/format";
import { cn } from "@/lib/utils";

type View = "open" | "mine" | "approval" | "hold";

function ReviewQueue() {
  const params = useSearchParams();
  const router = useRouter();
  const qc = useQueryClient();
  const { data: me } = useMe();
  const [view, setView] = React.useState<View>((params.get("view") as View) || "open");
  const { data, isLoading, error, refetch } = useReviewQueue(view);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => setSelected(new Set()), [view]);

  async function assignToMe() {
    if (!me) return;
    setBusy(true);
    const ids = Array.from(selected);
    const results = await Promise.allSettled(ids.map((id) => api.post(`/invoices/${id}/assign`, { assignee_id: me.id })));
    const ok = results.filter((r) => r.status === "fulfilled").length;
    toast.success(`Assigned ${ok} invoice${ok === 1 ? "" : "s"} to you`);
    setSelected(new Set());
    setBusy(false);
    qc.invalidateQueries({ queryKey: ["queue"] });
  }

  const PRIO: Record<string, number> = { HIGH: 0, NORMAL: 1, LOW: 2 };
  const t = useClientSort(data, {
    priority: (i) => PRIO[i.priority] ?? 3, invoice: (i) => i.reference, exception: (i) => i.reason_codes[0] ?? "",
    amount: (i) => (i.grand_total === null ? null : Number(i.grand_total)), status: (i) => i.status,
    assignee: (i) => i.assignee?.name ?? "", next: (i) => i.next_action ?? "", age: (i) => i.age_hours ?? 0,
  }, { sort: "priority", order: "asc" });
  const sp = { sort: t.sort, order: t.order, onSort: t.onSort };
  const rows = t.rows ?? [];
  const allChecked = rows.length > 0 && rows.every((r) => selected.has(r.id));
  const canAct = me?.role !== "AUDITOR";

  return (
    <div className="mx-auto max-w-[1440px]">
      <PageHeader title="Review queue" description="Invoices that need a person: exceptions to resolve, holds to clear, and approvals to give."
        actions={<Segmented value={view} onChange={setView} options={[
          { value: "open", label: "Needs action" }, { value: "mine", label: "Assigned to me" },
          { value: "approval", label: "Awaiting approval" }, { value: "hold", label: "On hold" }]} />} />
      <Card>
        {canAct && selected.size > 0 && (
          <div className="flex items-center justify-between border-b border-line bg-accent-soft px-4 py-2 text-[13px]">
            <span>{selected.size} selected</span>
            <Button size="sm" variant="primary" onClick={assignToMe} loading={busy}><CheckCheck className="size-3.5" />Assign to me</Button>
          </div>
        )}
        {error ? <div className="p-3"><ErrorState error={error} onRetry={() => refetch()} /></div> : (
          <Table>
            <THead><tr>
              {canAct && <Th className="w-8"><input type="checkbox" aria-label="Select all" checked={allChecked}
                onChange={() => setSelected(allChecked ? new Set() : new Set(rows.map((r) => r.id)))} /></Th>}
              <SortTh label="Priority" field="priority" {...sp} /><SortTh label="Invoice" field="invoice" {...sp} />
              <SortTh label="Exception" field="exception" {...sp} /><SortTh label="Amount at stake" field="amount" align="right" {...sp} />
              <SortTh label="Status" field="status" {...sp} /><SortTh label="Assignee" field="assignee" {...sp} />
              <SortTh label="Next action" field="next" {...sp} /><SortTh label="Age" field="age" align="right" {...sp} />
            </tr></THead>
            <tbody>
              {isLoading ? <SkeletonRows cols={9} /> : rows.map((i) => (
                <Tr key={i.id} onClick={() => router.push(`/invoices/${i.id}`)} className={cn(i.priority === "HIGH" && "bg-danger-soft/30")}>
                  {canAct && <Td onClick={(e) => e.stopPropagation()}><input type="checkbox" aria-label={`Select ${i.reference}`}
                    checked={selected.has(i.id)} onChange={() => setSelected((s) => { const n = new Set(s); if (n.has(i.id)) n.delete(i.id); else n.add(i.id); return n; })} /></Td>}
                  <Td><PriorityMark priority={i.priority} /></Td>
                  <Td><div className="flex items-center gap-2.5"><Avatar name={i.vendor?.legal_name ?? i.vendor_name_raw ?? "?"} /><div className="min-w-0">
                    <div className="font-medium">{i.reference}</div>
                    <div className="max-w-[200px] truncate text-[12px] text-ink-3">{i.vendor?.legal_name ?? i.vendor_name_raw ?? i.original_filename}</div></div></div></Td>
                  <Td><div className="flex flex-wrap gap-1">{i.reason_codes.slice(0, 2).map((c) => <ReasonChip key={c} code={c} />)}
                    {i.reason_codes.length > 2 && <span className="text-[12px] text-ink-3">+{i.reason_codes.length - 2}</span>}</div></Td>
                  <Td align="right" className="whitespace-nowrap">{money(i.grand_total, i.currency)}</Td>
                  <Td><StatusBadge status={i.status} /></Td>
                  <Td className="text-[12.5px]">{i.assignee?.name ?? <span className="text-ink-3">Unassigned</span>}</Td>
                  <Td><div className="max-w-[260px] truncate text-[12.5px] text-ink-2" title={i.next_action ?? ""}>{i.next_action}</div></Td>
                  <Td align="right" className={cn(i.age_hours && i.age_hours > 72 ? "text-warning font-medium" : "text-ink-2")}>{age(i.age_hours)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
        {!isLoading && rows.length === 0 && <EmptyState icon={<Inbox />} title="Nothing waiting here"
          description={view === "mine" ? "No invoices are assigned to you." : "When an invoice needs a decision from a person it appears in this queue."} />}
      </Card>
      <p className="mt-2 text-[12px] text-ink-3">Bulk actions are limited to assignment, which is safe and reversible. Decisions are made one invoice at a time.</p>
    </div>
  );
}

export default function ReviewPage() {
  return <React.Suspense><ReviewQueue /></React.Suspense>;
}
