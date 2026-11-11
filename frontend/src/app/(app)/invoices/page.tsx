"use client";
import { Download, FileStack, Search, Upload, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { PageHeader } from "@/components/layout/shell";
import { PriorityMark, StatusBadge } from "@/components/status/status";
import { Button } from "@/components/ui/button";
import { Card, EmptyState, ErrorState, Input, Select } from "@/components/ui/primitives";
import { Pagination, SkeletonRows, SortTh, Table, Td, Th, THead, Tr } from "@/components/ui/table";
import { qs } from "@/lib/api/client";
import { useInvoices, useMe, useVendors } from "@/lib/api/hooks";
import { ago, date, money } from "@/lib/format";
import { useDebounced } from "@/lib/hooks/use-debounced";

const STATUSES = [
  { value: "", label: "All statuses" }, { value: "READY_FOR_APPROVAL", label: "Ready for approval" },
  { value: "NEEDS_REVIEW", label: "Needs review" }, { value: "ON_HOLD", label: "On hold" },
  { value: "APPROVED", label: "Approved" }, { value: "REJECTED", label: "Rejected" },
  { value: "FAILED", label: "Technical failure" }, { value: "PROCESSING", label: "Processing" },
  { value: "CANCELLED", label: "Cancelled" },
];

export default function InvoicesPage() {
  const router = useRouter();
  const { data: me } = useMe();
  const [q, setQ] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [priority, setPriority] = React.useState("");
  const [vendor, setVendor] = React.useState("");
  const [from, setFrom] = React.useState("");
  const [to, setTo] = React.useState("");
  const [minAmt, setMinAmt] = React.useState("");
  const [maxAmt, setMaxAmt] = React.useState("");
  const [sort, setSort] = React.useState("created_at");
  const [order, setOrder] = React.useState("desc");
  const [page, setPage] = React.useState(1);
  const dq = useDebounced(q);
  const dMin = useDebounced(minAmt);
  const dMax = useDebounced(maxAmt);
  const { data: vendors } = useVendors({});
  const filters = { q: dq || undefined, status: status ? [status] : undefined, priority: priority || undefined,
    vendor_id: vendor || undefined, date_from: from || undefined, date_to: to || undefined,
    min_amount: dMin || undefined, max_amount: dMax || undefined, sort, order, page, page_size: 25 };
  const { data, isLoading, error, refetch } = useInvoices(filters);
  React.useEffect(() => setPage(1), [dq, status, priority, vendor, from, to, dMin, dMax]);
  const anyFilter = !!(q || status || priority || vendor || from || to || minAmt || maxAmt);

  function onSort(f: string) {
    if (sort === f) setOrder(order === "asc" ? "desc" : "asc");
    else { setSort(f); setOrder("desc"); }
  }
  function clear() { setQ(""); setStatus(""); setPriority(""); setVendor(""); setFrom(""); setTo(""); setMinAmt(""); setMaxAmt(""); }

  return (
    <div className="mx-auto max-w-[1440px]">
      <PageHeader title="Invoices" description="Every invoice received, its current status and what happens next."
        actions={<>
          <Button asChild variant="secondary"><a href={`/api/invoices/export.csv${qs({ q: dq, status: status ? [status] : undefined })}`}><Download />Export CSV</a></Button>
          {me?.role !== "AUDITOR" && <Button asChild variant="primary"><Link href="/invoices/new"><Upload />Upload</Link></Button>}
        </>} />
      <Card>
        <div className="flex flex-wrap items-end gap-2 border-b border-line p-3">
          <div className="relative min-w-[240px] flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-ink-3" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search invoice no., reference, vendor, PO…" className="pl-8" aria-label="Search" />
          </div>
          <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
            {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </Select>
          <Select value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="Priority">
            <option value="">Any priority</option><option value="HIGH">High</option><option value="NORMAL">Normal</option><option value="LOW">Low</option>
          </Select>
          <Select value={vendor} onChange={(e) => setVendor(e.target.value)} aria-label="Vendor" className="max-w-[200px]">
            <option value="">All vendors</option>
            {vendors?.items.map((v) => <option key={v.id} value={v.id}>{v.legal_name}</option>)}
          </Select>
          <div className="flex items-center gap-1">
            <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} aria-label="Invoice date from" className="w-[140px]" />
            <span className="text-ink-3">–</span>
            <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} aria-label="Invoice date to" className="w-[140px]" />
          </div>
          <div className="flex items-center gap-1">
            <Input inputMode="decimal" value={minAmt} onChange={(e) => setMinAmt(e.target.value.replace(/[^\d.]/g, ""))} placeholder="Min ₹" aria-label="Minimum amount" className="w-[96px]" />
            <span className="text-ink-3">–</span>
            <Input inputMode="decimal" value={maxAmt} onChange={(e) => setMaxAmt(e.target.value.replace(/[^\d.]/g, ""))} placeholder="Max ₹" aria-label="Maximum amount" className="w-[96px]" />
          </div>
          {anyFilter && <Button variant="ghost" onClick={clear}><X />Clear</Button>}
        </div>
        {error ? <div className="p-3"><ErrorState error={error} onRetry={() => refetch()} /></div> : (
          <>
            <Table>
              <THead><tr>
                <SortTh label="Reference" field="reference" sort={sort} order={order} onSort={onSort} />
                <Th>Vendor</Th><Th>Invoice no.</Th>
                <SortTh label="Invoice date" field="invoice_date" sort={sort} order={order} onSort={onSort} />
                <Th>PO</Th>
                <SortTh label="Amount" field="grand_total" sort={sort} order={order} onSort={onSort} align="right" />
                <SortTh label="Status" field="status" sort={sort} order={order} onSort={onSort} />
                <SortTh label="Priority" field="priority" sort={sort} order={order} onSort={onSort} />
                <Th>Next action</Th>
                <SortTh label="Received" field="created_at" sort={sort} order={order} onSort={onSort} />
              </tr></THead>
              <tbody>
                {isLoading ? <SkeletonRows cols={10} /> : data?.items.map((i) => (
                  <Tr key={i.id} onClick={() => router.push(`/invoices/${i.id}`)}>
                    <Td className="font-medium">{i.reference}</Td>
                    <Td><div className="max-w-[220px] truncate">{i.vendor?.legal_name ?? i.vendor_name_raw ?? <span className="text-ink-3">Unresolved</span>}</div>
                      {i.vendor && <div className="text-[11.5px] text-ink-3">{i.vendor.vendor_code}</div>}</Td>
                    <Td className="whitespace-nowrap font-mono text-[12px]">{i.invoice_number ?? <span className="text-ink-3">—</span>}</Td>
                    <Td className="num whitespace-nowrap">{date(i.invoice_date)}</Td>
                    <Td className="whitespace-nowrap font-mono text-[12px]">{i.po_number ?? "—"}</Td>
                    <Td align="right" className="whitespace-nowrap">{money(i.grand_total, i.currency)}</Td>
                    <Td><StatusBadge status={i.status} /></Td>
                    <Td><PriorityMark priority={i.priority} /></Td>
                    <Td><div className="max-w-[260px] truncate text-[12.5px] text-ink-2" title={i.next_action ?? ""}>{i.next_action ?? "—"}</div></Td>
                    <Td className="whitespace-nowrap text-[12px] text-ink-3">{ago(i.created_at)}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
            {!isLoading && data && data.total === 0 && (
              anyFilter ? <EmptyState icon={<Search />} title="No invoices match these filters" action={<Button onClick={clear}>Clear filters</Button>} />
                : <EmptyState icon={<FileStack />} title="No invoices yet" description="Uploaded invoices appear here with their live status." />
            )}
            {data && data.total > 0 && <Pagination page={page} pageSize={25} total={data.total} onPage={setPage} />}
          </>
        )}
      </Card>
    </div>
  );
}
