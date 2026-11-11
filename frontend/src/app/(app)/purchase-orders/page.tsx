"use client";
import { ClipboardList, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { PageHeader } from "@/components/layout/shell";
import { Segmented } from "@/components/ui/overlays";
import { Avatar, Card, EmptyState, ErrorState, Input, Mono } from "@/components/ui/primitives";
import { SkeletonRows, SortTh, Table, Td, THead, Tr, useClientSort } from "@/components/ui/table";
import { usePOs } from "@/lib/api/hooks";
import type { PurchaseOrder } from "@/lib/api/types";
import { date, humanize, money } from "@/lib/format";

import { ConsumptionBar, POStatusBadge, useDebounced } from "./_shared";

const STATUSES = [
  { value: "", label: "All" }, { value: "OPEN", label: "Open" }, { value: "CLOSED", label: "Closed" },
  { value: "CANCELLED", label: "Cancelled" },
];

export default function PurchaseOrdersPage() {
  const router = useRouter();
  const [search, setSearch] = React.useState("");
  const [status, setStatus] = React.useState("");
  const q = useDebounced(search);
  const { data, isLoading, isError, error, refetch } = usePOs({ q: q || undefined, status: status || undefined, page: 1 });
  const t = useClientSort(data?.items, {
    po: (p) => p.po_number, vendor: (p) => p.vendor.legal_name, description: (p) => p.description, type: (p) => p.po_type,
    date: (p) => p.po_date, value: (p) => Number(p.subtotal), invoiced: (p) => Number(p.invoiced_value),
    remaining: (p) => Number(p.remaining_value), grns: (p) => p.grn_count, status: (p) => p.status,
  }, { sort: "date", order: "desc" });
  const sp = { sort: t.sort, order: t.order, onSort: t.onSort };

  return (
    <div>
      <PageHeader title="Purchase orders"
        description="Fictional PO register for Kestrel Components. Invoices are reconciled against these lines and their goods receipts." />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-3" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search PO, vendor, description"
            className="pl-8" aria-label="Search purchase orders" />
        </div>
        <Segmented value={status} onChange={setStatus} options={STATUSES} />
      </div>
      {isError ? <ErrorState error={error} onRetry={() => refetch()} /> : (
        <Card className="overflow-hidden">
          <Table>
            <THead>
              <tr>
                <SortTh label="PO number" field="po" {...sp} /><SortTh label="Vendor" field="vendor" {...sp} />
                <SortTh label="Description" field="description" {...sp} /><SortTh label="Type" field="type" {...sp} />
                <SortTh label="PO date" field="date" {...sp} /><SortTh label="Value (pre-tax)" field="value" align="right" {...sp} />
                <SortTh label="Invoiced" field="invoiced" align="right" {...sp} />
                <SortTh label="Remaining" field="remaining" align="right" {...sp} />
                <SortTh label="GRNs" field="grns" align="right" {...sp} /><SortTh label="Status" field="status" {...sp} />
              </tr>
            </THead>
            <tbody>
              {isLoading ? <SkeletonRows cols={10} /> : t.rows?.map((po: PurchaseOrder) => (
                <Tr key={po.id} onClick={() => router.push(`/purchase-orders/${po.id}`)}>
                  <Td><Mono className="text-ink">{po.po_number}</Mono></Td>
                  <Td>
                    <div className="flex items-center gap-2.5"><Avatar name={po.vendor.legal_name} /><div className="min-w-0">
                    <div className="max-w-[200px] truncate font-medium">{po.vendor.legal_name}</div>
                    <div className="text-[12px] text-ink-3">{po.vendor.vendor_code}</div></div></div>
                  </Td>
                  <Td className="max-w-[260px] truncate text-ink-2">{po.description}</Td>
                  <Td className="text-ink-2">{humanize(po.po_type)}</Td>
                  <Td className="whitespace-nowrap text-ink-2">{date(po.po_date)}</Td>
                  <Td align="right">{money(po.subtotal, po.currency)}</Td>
                  <Td align="right" className="text-ink-2">{money(po.invoiced_value, po.currency)}</Td>
                  <Td align="right">
                    <div className="flex flex-col items-end gap-1">
                      <span>{money(po.remaining_value, po.currency)}</span>
                      <ConsumptionBar used={po.invoiced_value} total={po.subtotal} />
                    </div>
                  </Td>
                  <Td align="right" className="text-ink-2">{po.grn_count}</Td>
                  <Td><POStatusBadge status={po.status} /></Td>
                </Tr>
              ))}
            </tbody>
          </Table>
          {!isLoading && data && data.items.length === 0 && (
            <EmptyState icon={<ClipboardList />} title="No purchase orders match"
              description={q || status ? "Try a different search or status filter." : "Run the seed command to load the demo PO register."} />
          )}
          {data && data.total > 0 && <div className="px-4 py-3 text-[12px] text-ink-3">{data.total} purchase order{data.total === 1 ? "" : "s"} · values exclude GST</div>}
        </Card>
      )}
    </div>
  );
}
