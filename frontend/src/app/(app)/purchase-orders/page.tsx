"use client";
import { ClipboardList, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { PageHeader } from "@/components/layout/shell";
import { Segmented, Tip } from "@/components/ui/overlays";
import { Card, EmptyState, ErrorState, Input, Mono } from "@/components/ui/primitives";
import { Pagination, SkeletonRows, Table, Td, Th, THead, Tr } from "@/components/ui/table";
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
  const [page, setPage] = React.useState(1);
  const q = useDebounced(search);
  React.useEffect(() => setPage(1), [q, status]);
  const { data, isLoading, isError, error, refetch } = usePOs({ q: q || undefined, status: status || undefined, page });

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
                <Th>PO number</Th><Th>Vendor</Th><Th>Description</Th><Th>Type</Th><Th>PO date</Th>
                <Th align="right"><Tip content="PO subtotal before GST"><span>Value (pre-tax)</span></Tip></Th>
                <Th align="right">Invoiced</Th><Th align="right">Remaining</Th><Th align="right">GRNs</Th><Th>Status</Th>
              </tr>
            </THead>
            <tbody>
              {isLoading ? <SkeletonRows cols={10} /> : data?.items.map((po: PurchaseOrder) => (
                <Tr key={po.id} onClick={() => router.push(`/purchase-orders/${po.id}`)}>
                  <Td><Mono className="text-ink">{po.po_number}</Mono></Td>
                  <Td>
                    <div className="max-w-[220px] truncate">{po.vendor.legal_name}</div>
                    <div className="text-[12px] text-ink-3">{po.vendor.vendor_code}</div>
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
          {data && data.total > 0 && (
            <div className="border-t border-line">
              <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
