"use client";
import { Building2, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { PageHeader } from "@/components/layout/shell";
import { VendorStatus } from "@/components/status/status";
import { Segmented } from "@/components/ui/overlays";
import { Avatar, Card, EmptyState, ErrorState, Input, Mono } from "@/components/ui/primitives";
import { SkeletonRows, SortTh, Table, Td, THead, Tr, useClientSort } from "@/components/ui/table";
import { useVendors } from "@/lib/api/hooks";
import { money } from "@/lib/format";

import { useDebounced } from "../purchase-orders/_shared";

const STATUSES = [
  { value: "", label: "All" }, { value: "APPROVED", label: "Approved" },
  { value: "PENDING_ONBOARDING", label: "Pending onboarding" }, { value: "BLOCKED", label: "Blocked" },
];

export default function VendorsPage() {
  const router = useRouter();
  const [search, setSearch] = React.useState("");
  const [status, setStatus] = React.useState("");
  const page = 1;
  const q = useDebounced(search);
  const { data, isLoading, isError, error, refetch } = useVendors({ q: q || undefined, status: status || undefined, page });
  const t = useClientSort(data?.items, {
    code: (v) => v.vendor_code, name: (v) => v.legal_name, location: (v) => v.city, gstin: (v) => v.tax_id_masked,
    status: (v) => v.approved_status, pos: (v) => v.open_po_count, invoices: (v) => v.invoice_count,
    value: (v) => Number(v.open_invoice_value), bank: (v) => v.bank_details_version,
  }, { sort: "code", order: "asc" });
  const sp = { sort: t.sort, order: t.order, onSort: t.onSort };

  return (
    <div>
      <PageHeader title="Vendors"
        description="Vendor master with verified remittance details. Identifiers are masked; invoices never update this record." />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-3" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, code, city"
            className="pl-8" aria-label="Search vendors" />
        </div>
        <Segmented value={status} onChange={setStatus} options={STATUSES} />
      </div>
      {isError ? <ErrorState error={error} onRetry={() => refetch()} /> : (
        <Card className="overflow-hidden">
          <Table>
            <THead>
              <tr>
                <SortTh label="Code" field="code" {...sp} /><SortTh label="Vendor" field="name" {...sp} />
                <SortTh label="Location" field="location" {...sp} /><SortTh label="GSTIN" field="gstin" {...sp} />
                <SortTh label="Status" field="status" {...sp} /><SortTh label="Open POs" field="pos" align="right" {...sp} />
                <SortTh label="Invoices" field="invoices" align="right" {...sp} />
                <SortTh label="Open invoice value" field="value" align="right" {...sp} /><SortTh label="Bank" field="bank" {...sp} />
              </tr>
            </THead>
            <tbody>
              {isLoading ? <SkeletonRows cols={9} /> : t.rows?.map((v) => (
                <Tr key={v.id} onClick={() => router.push(`/vendors/${v.id}`)}>
                  <Td><Mono className="text-ink-2">{v.vendor_code}</Mono></Td>
                  <Td>
                    <div className="flex items-center gap-2.5"><Avatar name={v.legal_name} /><div className="min-w-0">
                    <div className="max-w-[260px] truncate font-medium">{v.legal_name}</div>
                    <div className="text-[12px] text-ink-3">{v.category}</div></div></div>
                  </Td>
                  <Td className="whitespace-nowrap text-ink-2">{v.city}{v.state_code ? ` · ${v.state_code}` : ""}</Td>
                  <Td><Mono className="text-ink-2">{v.tax_id_masked ?? "—"}</Mono></Td>
                  <Td><VendorStatus status={v.approved_status} /></Td>
                  <Td align="right" className="text-ink-2">{v.open_po_count}</Td>
                  <Td align="right" className="text-ink-2">{v.invoice_count}</Td>
                  <Td align="right">{Number(v.open_invoice_value) ? money(v.open_invoice_value, v.currency) : "—"}</Td>
                  <Td className="whitespace-nowrap text-ink-2">
                    {v.bank_account_last4 ? <><Mono>••••{v.bank_account_last4}</Mono>
                      <span className="ml-1.5 text-[11.5px] text-ink-3">v{v.bank_details_version}</span></> : "—"}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
          {!isLoading && data && data.items.length === 0 && (
            <EmptyState icon={<Building2 />} title="No vendors match"
              description={q || status ? "Try a different search or status filter." : "Run the seed command to load demo vendors."} />
          )}
          {data && data.total > 0 && <div className="px-4 py-3 text-[12px] text-ink-3">{data.total} vendor{data.total === 1 ? "" : "s"}</div>}
        </Card>
      )}
    </div>
  );
}
