"use client";
import { FileStack, PackageCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { PageHeader } from "@/components/layout/shell";
import { Badge, StatusBadge } from "@/components/status/status";
import { Card, CardHeader, EmptyState, ErrorState, Kv, Mono, Skeleton } from "@/components/ui/primitives";
import { Table, Td, Th, THead, Tr } from "@/components/ui/table";
import { usePO } from "@/lib/api/hooks";
import { date, humanize, money, qty } from "@/lib/format";

import { ConsumptionBar, POStatusBadge } from "../_shared";

export default function PODetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: po, isLoading, isError, error, refetch } = usePO(id);

  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (isLoading || !po) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-32" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  const goods = po.po_type === "GOODS";
  const lineNo = new Map(po.lines.map((l) => [l.line_number, l]));

  return (
    <div className="space-y-4">
      <PageHeader
        crumbs={[{ href: "/purchase-orders", label: "Purchase orders" }, { label: po.po_number }]}
        title={<span className="flex flex-wrap items-center gap-2.5"><span className="font-mono">{po.po_number}</span>
          <POStatusBadge status={po.status} /></span>}
        description={<>{po.description} · <Link href={`/vendors/${po.vendor.id}`} className="text-accent hover:underline">
          {po.vendor.legal_name}</Link> <span className="text-ink-3">({po.vendor.vendor_code})</span></>}
      />

      <Card className="p-4">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-6">
          <Kv label="Vendor"><Link href={`/vendors/${po.vendor.id}`} className="text-accent hover:underline">
            {po.vendor.legal_name}</Link></Kv>
          <Kv label="Type">{humanize(po.po_type)} · {goods ? "three-way match" : "two-way match"}</Kv>
          <Kv label="PO date">{date(po.po_date)}</Kv>
          <Kv label="Valid until">{date(po.valid_until)}</Kv>
          <Kv label="Requester">{po.requester}</Kv>
          <Kv label="Cost centre"><Mono>{po.cost_centre}</Mono></Kv>
          <Kv label="Subtotal"><span className="num">{money(po.subtotal, po.currency)}</span></Kv>
          <Kv label="GST"><span className="num">{money(po.tax_total, po.currency)}</span></Kv>
          <Kv label="Total"><span className="num font-medium">{money(po.total_amount, po.currency)}</span></Kv>
          <Kv label="Invoiced (pre-tax)"><span className="num">{money(po.invoiced_value, po.currency)}</span></Kv>
          <Kv label="Remaining (pre-tax)">
            <span className="flex items-center gap-2"><span className="num">{money(po.remaining_value, po.currency)}</span>
              <ConsumptionBar used={po.invoiced_value} total={po.subtotal} /></span>
          </Kv>
          <Kv label="Goods receipts">{goods ? po.goods_receipts.length : "Not applicable"}</Kv>
        </dl>
        <p className="mt-3 border-t border-line pt-3 text-[12px] text-ink-3">
          Invoiced figures count only invoice amounts that are reserved (ready for approval) or approved against this
          PO. Invoices still in review or on hold do not consume the PO balance.
        </p>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="Lines" description={goods
          ? "Ordered vs received (goods receipts) vs invoiced. Remaining = ordered − invoiced."
          : "Services PO: no goods receipts; reconciliation is two-way (invoice vs PO)."} />
        <Table>
          <THead>
            <tr>
              <Th>#</Th><Th>Item code</Th><Th>Description</Th><Th>Unit</Th><Th align="right">Unit price</Th>
              <Th align="right">GST %</Th><Th align="right">Ordered</Th><Th align="right">Received</Th>
              <Th align="right">Invoiced</Th><Th align="right">Remaining</Th>
            </tr>
          </THead>
          <tbody>
            {po.lines.map((l) => (
              <Tr key={l.id}>
                <Td className="text-ink-3">{l.line_number}</Td>
                <Td><Mono className="text-ink-2">{l.item_code ?? "—"}</Mono></Td>
                <Td className="max-w-[320px]">{l.description}</Td>
                <Td className="text-ink-2">{l.unit}</Td>
                <Td align="right">{money(l.unit_price, null)}</Td>
                <Td align="right" className="text-ink-2">{qty(l.tax_rate)}</Td>
                <Td align="right">{qty(l.quantity_ordered)}</Td>
                <Td align="right" className="text-ink-2">{goods ? qty(l.quantity_received ?? "0") : "—"}</Td>
                <Td align="right" className="text-ink-2">{qty(l.quantity_invoiced)}</Td>
                <Td align="right">
                  <div className="flex flex-col items-end gap-1">
                    <span>{qty(l.quantity_remaining)}</span>
                    <ConsumptionBar used={l.quantity_invoiced} total={l.quantity_ordered} className="w-12" />
                  </div>
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="overflow-hidden">
          <CardHeader title="Goods receipts" description="Posted receipts used for three-way matching." />
          {!goods ? (
            <EmptyState icon={<PackageCheck />} title="Not applicable" description="Services are not receipted; invoices are matched two-way." />
          ) : po.goods_receipts.length === 0 ? (
            <EmptyState icon={<PackageCheck />} title="No goods received yet"
              description="Invoices against this PO are held (GRN pending) until a receipt is posted." />
          ) : (
            <Table>
              <THead>
                <tr><Th>GRN</Th><Th>Received</Th><Th>Received by</Th><Th>Warehouse</Th><Th>Lines received</Th></tr>
              </THead>
              <tbody>
                {po.goods_receipts.map((g) => (
                  <Tr key={g.grn_number}>
                    <Td><Mono>{g.grn_number}</Mono></Td>
                    <Td className="whitespace-nowrap text-ink-2">{date(g.received_date)}</Td>
                    <Td className="text-ink-2">{g.received_by}</Td>
                    <Td className="text-ink-2">{g.warehouse}</Td>
                    <Td className="text-[12px] text-ink-2">
                      {g.lines.map((gl) => (
                        <div key={gl.po_line} className="num">
                          L{gl.po_line}: {qty(gl.quantity_received)} {lineNo.get(gl.po_line)?.unit ?? ""}
                        </div>
                      ))}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        <Card className="overflow-hidden">
          <CardHeader title="Invoices against this PO"
            description="Consumption shows whether the invoice currently holds part of the PO balance." />
          {po.invoices.length === 0 ? (
            <EmptyState icon={<FileStack />} title="No invoices yet" description="No invoice has been matched to this PO." />
          ) : (
            <Table>
              <THead>
                <tr><Th>Reference</Th><Th>Invoice no.</Th><Th>Status</Th><Th align="right">Amount consumed</Th><Th>Consumption</Th></tr>
              </THead>
              <tbody>
                {po.invoices.map((i) => (
                  <Tr key={`${i.id}-${i.consumption}`}>
                    <Td><Link href={`/invoices/${i.id}`} className="font-mono text-[12px] text-accent hover:underline">{i.reference}</Link></Td>
                    <Td><Mono className="text-ink-2">{i.invoice_number ?? "—"}</Mono></Td>
                    <Td><StatusBadge status={i.status} /></Td>
                    <Td align="right">{i.consumption === "NONE" ? "—" : money(i.amount_consumed, po.currency)}</Td>
                    <Td>
                      <Badge tone={i.consumption === "APPROVED" ? "accent" : i.consumption === "RESERVED" ? "success" : "neutral"}>
                        {i.consumption === "NONE" ? "Not consuming" : humanize(i.consumption)}
                      </Badge>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      </div>
    </div>
  );
}
