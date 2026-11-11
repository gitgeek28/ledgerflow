"use client";
import { FileStack, PackageCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { PageHeader } from "@/components/layout/shell";
import { Badge, StatusBadge } from "@/components/status/status";
import { Card, CardHeader, EmptyState, ErrorState, Kv, Mono, Skeleton } from "@/components/ui/primitives";
import { SortTh, Table, Td, THead, Tr, useClientSort } from "@/components/ui/table";
import { usePO } from "@/lib/api/hooks";
import { date, humanize, money, qty } from "@/lib/format";

import { ConsumptionBar, POStatusBadge } from "../_shared";

export default function PODetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: po, isLoading, isError, error, refetch } = usePO(id);
  const n = (v: string | null | undefined) => (v === null || v === undefined ? null : Number(v));
  const lt = useClientSort(po?.lines, {
    no: (l) => l.line_number, code: (l) => l.item_code, desc: (l) => l.description, unit: (l) => l.unit,
    price: (l) => n(l.unit_price), gst: (l) => n(l.tax_rate), ordered: (l) => n(l.quantity_ordered),
    received: (l) => n(l.quantity_received), invoiced: (l) => n(l.quantity_invoiced), remaining: (l) => n(l.quantity_remaining),
  }, { sort: "no", order: "asc" });
  const gt = useClientSort(po?.goods_receipts, {
    grn: (g) => g.grn_number, date: (g) => g.received_date, by: (g) => g.received_by, wh: (g) => g.warehouse,
    lines: (g) => g.lines.length,
  }, { sort: "date", order: "asc" });
  const it = useClientSort(po?.invoices, {
    ref: (i) => i.reference, no: (i) => i.invoice_number, status: (i) => i.status, amount: (i) => n(i.amount_consumed),
    cons: (i) => i.consumption,
  }, { sort: "ref", order: "asc" });

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
              <SortTh label="#" field="no" {...lt} /><SortTh label="Item code" field="code" {...lt} />
              <SortTh label="Description" field="desc" {...lt} /><SortTh label="Unit" field="unit" {...lt} />
              <SortTh label="Unit price" field="price" align="right" {...lt} /><SortTh label="GST %" field="gst" align="right" {...lt} />
              <SortTh label="Ordered" field="ordered" align="right" {...lt} /><SortTh label="Received" field="received" align="right" {...lt} />
              <SortTh label="Invoiced" field="invoiced" align="right" {...lt} /><SortTh label="Remaining" field="remaining" align="right" {...lt} />
            </tr>
          </THead>
          <tbody>
            {(lt.rows ?? []).map((l) => (
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
                <tr><SortTh label="GRN" field="grn" {...gt} /><SortTh label="Received" field="date" {...gt} />
                  <SortTh label="Received by" field="by" {...gt} /><SortTh label="Warehouse" field="wh" {...gt} />
                  <SortTh label="Lines received" field="lines" {...gt} /></tr>
              </THead>
              <tbody>
                {(gt.rows ?? []).map((g) => (
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
                <tr><SortTh label="Reference" field="ref" {...it} /><SortTh label="Invoice no." field="no" {...it} />
                  <SortTh label="Status" field="status" {...it} /><SortTh label="Amount consumed" field="amount" align="right" {...it} />
                  <SortTh label="Consumption" field="cons" {...it} /></tr>
              </THead>
              <tbody>
                {(it.rows ?? []).map((i) => (
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
