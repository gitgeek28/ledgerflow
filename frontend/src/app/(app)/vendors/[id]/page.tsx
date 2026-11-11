"use client";
import { AlertTriangle, ClipboardList, FileStack, Landmark, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { PageHeader } from "@/components/layout/shell";
import { StatusBadge, VendorStatus } from "@/components/status/status";
import { Card, CardHeader, EmptyState, ErrorState, Kv, Mono, Skeleton } from "@/components/ui/primitives";
import { Table, Td, Th, THead, Tr } from "@/components/ui/table";
import { useVendor } from "@/lib/api/hooks";
import { ago, date, humanize, money } from "@/lib/format";
import { cn } from "@/lib/utils";

import { ConsumptionBar, POStatusBadge } from "../../purchase-orders/_shared";

export default function VendorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data, isLoading, isError, error, refetch } = useVendor(id);

  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (isLoading || !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-36" />
        <Skeleton className="h-56" />
      </div>
    );
  }
  const { vendor: v, purchase_orders: pos, invoices, bank_change_alerts } = data;
  const blocked = v.approved_status === "BLOCKED";

  return (
    <div className="space-y-4">
      <PageHeader
        crumbs={[{ href: "/vendors", label: "Vendors" }, { label: v.vendor_code }]}
        title={<span className="flex flex-wrap items-center gap-2.5">{v.legal_name}<VendorStatus status={v.approved_status} /></span>}
        description={`${v.vendor_code} · ${v.category} · ${v.city}`}
      />

      {v.approved_status !== "APPROVED" && (
        <div role="status" className={cn("flex items-start gap-2.5 rounded-md border px-4 py-3 text-[13px]",
          blocked ? "border-danger/30 bg-danger-soft text-danger" : "border-warning/30 bg-warning-soft text-warning")}>
          {blocked ? <ShieldAlert className="mt-0.5 size-4 shrink-0" /> : <AlertTriangle className="mt-0.5 size-4 shrink-0" />}
          <div>
            <p className="font-medium">{blocked ? "Blocked vendor: invoices are rejected by policy"
              : "Onboarding incomplete: invoices are held"}</p>
            {v.status_reason && <p className="mt-0.5 opacity-90">{v.status_reason}</p>}
          </div>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="p-4 xl:col-span-2">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
            <Kv label="Vendor code"><Mono>{v.vendor_code}</Mono></Kv>
            <Kv label="Legal name">{v.legal_name}</Kv>
            <Kv label="Display name">{v.display_name}</Kv>
            <Kv label="GSTIN (masked)"><Mono>{v.tax_id_masked ?? "—"}</Mono></Kv>
            <Kv label="State code">{v.state_code ?? "—"}</Kv>
            <Kv label="City">{v.city}</Kv>
            <Kv label="Category">{v.category}</Kv>
            <Kv label="Currency">{v.currency}</Kv>
            <Kv label="Payment terms">{v.payment_terms_days} days</Kv>
            <div className="col-span-2 sm:col-span-3">
              <dt className="text-[11.5px] font-medium uppercase tracking-wide text-ink-3">Registered aliases</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {v.aliases.length ? v.aliases.map((a) => (
                  <span key={a} className="rounded-[5px] border border-line bg-surface-2 px-1.5 py-0.5 text-[12px] text-ink-2">{a}</span>
                )) : <span className="text-[13px] text-ink-3">None</span>}
              </dd>
            </div>
          </dl>
        </Card>

        <Card>
          <CardHeader title="Verified remittance details" description="Payments use these details, never the ones printed on an invoice." />
          <div className="space-y-3 p-4">
            <div className="flex items-center gap-3">
              <span className="flex size-9 items-center justify-center rounded-md bg-surface-3 text-ink-2"><Landmark className="size-4" /></span>
              <div>
                <div className="text-[13px] font-medium">{v.bank_name ?? "No bank details on file"}</div>
                {v.bank_account_last4 && <div className="text-[12px] text-ink-3">Account <Mono>••••{v.bank_account_last4}</Mono>
                  {v.bank_ifsc && <> · IFSC <Mono>{v.bank_ifsc}</Mono></>}</div>}
              </div>
            </div>
            <dl className="grid grid-cols-2 gap-3">
              <Kv label="Version">v{v.bank_details_version}</Kv>
              <Kv label="Last verified">{v.bank_details_updated_at ? date(v.bank_details_updated_at) : "—"}</Kv>
            </dl>
            {bank_change_alerts > 0 && (
              <div className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-[12.5px] text-danger">
                <ShieldAlert className="mt-0.5 size-4 shrink-0" />
                <span>{bank_change_alerts} invoice{bank_change_alerts === 1 ? "" : "s"} requested payment to different bank
                  details. The vendor master is never updated from an invoice.</span>
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <CardHeader title="Purchase orders" description={`${pos.length} PO${pos.length === 1 ? "" : "s"} issued to this vendor`} />
        {pos.length === 0 ? <EmptyState icon={<ClipboardList />} title="No purchase orders" /> : (
          <Table>
            <THead>
              <tr><Th>PO number</Th><Th>Description</Th><Th>Type</Th><Th>PO date</Th><Th align="right">Value (pre-tax)</Th>
                <Th align="right">Remaining</Th><Th>Status</Th></tr>
            </THead>
            <tbody>
              {pos.map((po) => (
                <Tr key={po.id} onClick={() => router.push(`/purchase-orders/${po.id}`)}>
                  <Td><Mono>{po.po_number}</Mono></Td>
                  <Td className="max-w-[300px] truncate text-ink-2">{po.description}</Td>
                  <Td className="text-ink-2">{humanize(po.po_type)}</Td>
                  <Td className="whitespace-nowrap text-ink-2">{date(po.po_date)}</Td>
                  <Td align="right">{money(po.subtotal, po.currency)}</Td>
                  <Td align="right">
                    <div className="flex flex-col items-end gap-1">
                      <span>{money(po.remaining_value, po.currency)}</span>
                      <ConsumptionBar used={po.invoiced_value} total={po.subtotal} />
                    </div>
                  </Td>
                  <Td><POStatusBadge status={po.status} /></Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="Recent invoices" description="Most recent 50 invoices resolved to this vendor" />
        {invoices.length === 0 ? <EmptyState icon={<FileStack />} title="No invoices yet" /> : (
          <Table>
            <THead>
              <tr><Th>Reference</Th><Th>Invoice no.</Th><Th>Invoice date</Th><Th>PO</Th><Th align="right">Amount</Th>
                <Th>Status</Th><Th>Received</Th></tr>
            </THead>
            <tbody>
              {invoices.map((i) => (
                <Tr key={i.id} onClick={() => router.push(`/invoices/${i.id}`)}>
                  <Td><Link href={`/invoices/${i.id}`} onClick={(e) => e.stopPropagation()}
                    className="font-mono text-[12px] text-accent hover:underline">{i.reference}</Link></Td>
                  <Td><Mono className="text-ink-2">{i.invoice_number ?? "—"}</Mono></Td>
                  <Td className="whitespace-nowrap text-ink-2">{date(i.invoice_date)}</Td>
                  <Td><Mono className="text-ink-2">{i.po_number ?? "—"}</Mono></Td>
                  <Td align="right">{money(i.grand_total, i.currency)}</Td>
                  <Td><StatusBadge status={i.status} /></Td>
                  <Td className="whitespace-nowrap text-ink-3">{ago(i.created_at)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
