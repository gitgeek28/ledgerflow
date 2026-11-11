"use client";
import { Building2, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { PageHeader } from "@/components/layout/shell";
import { VendorStatus } from "@/components/status/status";
import { Segmented } from "@/components/ui/overlays";
import { Card, EmptyState, ErrorState, Input, Mono } from "@/components/ui/primitives";
import { Pagination, SkeletonRows, Table, Td, Th, THead, Tr } from "@/components/ui/table";
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
  const [page, setPage] = React.useState(1);
  const q = useDebounced(search);
  React.useEffect(() => setPage(1), [q, status]);
  const { data, isLoading, isError, error, refetch } = useVendors({ q: q || undefined, status: status || undefined, page });

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
                <Th>Code</Th><Th>Vendor</Th><Th>Location</Th><Th>GSTIN</Th><Th>Status</Th>
                <Th align="right">Open POs</Th><Th align="right">Invoices</Th><Th align="right">Open invoice value</Th>
                <Th>Bank</Th>
              </tr>
            </THead>
            <tbody>
              {isLoading ? <SkeletonRows cols={9} /> : data?.items.map((v) => (
                <Tr key={v.id} onClick={() => router.push(`/vendors/${v.id}`)}>
                  <Td><Mono className="text-ink-2">{v.vendor_code}</Mono></Td>
                  <Td>
                    <div className="max-w-[260px] truncate">{v.legal_name}</div>
                    <div className="text-[12px] text-ink-3">{v.category}</div>
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
