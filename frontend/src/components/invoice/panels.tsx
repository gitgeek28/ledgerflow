"use client";
import { Bot, Check, Copy, Cpu, Crosshair, Pencil, Send, User as UserIcon, X } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { toast } from "sonner";

import type { Highlight } from "@/components/pdf/pdf-viewer";
import { Badge, CheckIcon, Confidence, RunStatusBadge, SeverityBadge, StatusBadge } from "@/components/status/status";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, Input, SectionTitle, Textarea } from "@/components/ui/primitives";
import { SortTh, Table, Td, Th, THead, useClientSort } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api/client";
import { useInvoiceAudit, useReviewAction, useVendors } from "@/lib/api/hooks";
import type { Check as CheckT, ExtractedField, InvoiceDetail } from "@/lib/api/types";
import { ago, date, dateTime, humanize, money, ms, qty, STAGE_LABEL, STAGES } from "@/lib/format";
import { cn } from "@/lib/utils";

const FIELDS: { key: string; label: string; kind?: "money" | "date"; editable?: boolean; critical?: boolean }[] = [
  { key: "vendor_name", label: "Supplier name", editable: true },
  { key: "vendor_tax_id", label: "Supplier GSTIN", editable: true },
  { key: "invoice_number", label: "Invoice number", editable: true, critical: true },
  { key: "invoice_date", label: "Invoice date", kind: "date", editable: true, critical: true },
  { key: "due_date", label: "Due date", kind: "date", editable: true },
  { key: "po_number", label: "PO reference", editable: true },
  { key: "currency", label: "Currency", editable: true },
  { key: "subtotal", label: "Subtotal", kind: "money", editable: true },
  { key: "tax_total", label: "Tax total", kind: "money", editable: true },
  { key: "grand_total", label: "Grand total", kind: "money", editable: true, critical: true },
  { key: "bank_account", label: "Remittance account" },
  { key: "bank_ifsc", label: "Remittance IFSC" },
];
const OPEN = ["NEEDS_REVIEW", "ON_HOLD", "READY_FOR_APPROVAL"];

function show(value: string | null | undefined, kind?: string, currency?: string | null) {
  if (value === null || value === undefined) return null;
  if (kind === "money") return money(value, currency);
  if (kind === "date") return date(value);
  return value;
}

function useAct(inv: InvoiceDetail, onRun: (runId: string) => void) {
  const m = useReviewAction(inv.id);
  return async (body: Parameters<typeof m.mutateAsync>[0], ok?: string) => {
    try {
      const r = await m.mutateAsync(body);
      toast.success(ok ?? r.message);
      if (r.run_id) onRun(r.run_id);
      return r;
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Action failed");
      return null;
    }
  };
}

// ------------------------------------------------------------------------------------------------ fields
export function FieldsPanel({ inv, threshold, onEvidence, onRun }: { inv: InvoiceDetail; threshold: number;
  onEvidence: (h: Highlight) => void; onRun: (id: string) => void }) {
  const act = useAct(inv, onRun);
  const [editing, setEditing] = React.useState<string | null>(null);
  const [draft, setDraft] = React.useState("");
  const [reason, setReason] = React.useState("");
  const fields = inv.extraction?.fields ?? {};
  const canEdit = inv.permissions.can_act && OPEN.includes(inv.status);
  const issues = inv.extraction?.issues ?? [];
  const num = (v: string | null | undefined) => (v === null || v === undefined ? null : Number(v));
  const lt = useClientSort(inv.lines, {
    no: (l) => l.line_number, desc: (l) => l.description, qty: (l) => num(l.quantity), unit: (l) => l.unit,
    rate: (l) => num(l.unit_price), gst: (l) => num(l.tax_rate), amount: (l) => num(l.line_subtotal),
    conf: (l) => num(l.extraction_confidence),
  }, { sort: "no", order: "asc" });
  const llm = inv.extraction?.llm as { status?: string; model?: string; accepted?: string[]; rejected?: { field: string; reason: string }[] } | null;

  return (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-2 text-[12px] text-ink-3">
        <Cpu className="size-3.5" /><span>Extractor: <span className="text-ink-2">{inv.extraction?.extractor ?? "—"}</span></span>
        {inv.document_text?.pages?.map((p) => (
          <Badge key={p.page} tone={p.method === "ocr" ? "warning" : "neutral"} className="h-5 text-[11px]">
            p{p.page}: {p.method === "ocr" ? `OCR ${p.mean_confidence?.toFixed(2) ?? ""}` : "text layer"}</Badge>
        ))}
      </div>
      {llm && (
        <div className="flex items-start gap-2 rounded-md border border-line bg-surface-2 px-3 py-2 text-[12px] text-ink-2">
          <Bot className="mt-0.5 size-4 text-ink-3" />
          <div>Local model fallback ({llm.model}) was consulted for missing critical fields: <b>{llm.status}</b>.
            {llm.accepted?.length ? ` Accepted (verified verbatim in the document): ${llm.accepted.join(", ")}.` : " No value was accepted."}
            {llm.rejected?.length ? ` Rejected: ${llm.rejected.map((r) => `${r.field} (${r.reason})`).join("; ")}.` : ""}</div>
        </div>
      )}
      <div className="overflow-hidden rounded-md border border-line">
        <table className="w-full text-[13px]">
          <tbody>
            {FIELDS.map((f) => {
              const ex: ExtractedField | undefined = fields[f.key];
              const ov = inv.field_overrides[f.key];
              const value = ov ? (ov.unreadable ? null : ov.value) : ex?.value ?? null;
              const conf = ov ? (ov.unreadable ? 0 : 1) : ex?.confidence ?? 0;
              const method = ov ? "human" : ex?.method;
              const low = !ov && value !== null && conf < threshold && f.critical;
              return (
                <tr key={f.key} className={cn("border-b border-line last:border-0", low && "bg-warning-soft/60",
                  !value && f.critical && "bg-danger-soft/50")}>
                  <td className="w-[150px] px-3 py-2 align-top text-[12.5px] text-ink-3">{f.label}{f.critical && <span className="text-danger"> *</span>}</td>
                  <td className="px-3 py-2 align-top">
                    {editing === f.key ? (
                      <form className="space-y-1.5" onSubmit={async (e) => {
                        e.preventDefault();
                        const r = await act({ action: "CORRECT_FIELD", field: f.key, value: draft, reason: reason || undefined },
                          `${f.label} corrected; re-running checks`);
                        if (r) { setEditing(null); setReason(""); }
                      }}>
                        <Input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
                          placeholder={f.kind === "date" ? "YYYY-MM-DD" : f.kind === "money" ? "0.00" : ""} aria-label={`New ${f.label}`} />
                        <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason / source (optional)" aria-label="Reason" />
                        <div className="flex gap-1.5">
                          <Button size="sm" variant="primary" type="submit"><Check className="size-3.5" />Save & re-check</Button>
                          <Button size="sm" variant="ghost" type="button" onClick={() => setEditing(null)}><X className="size-3.5" />Cancel</Button>
                        </div>
                      </form>
                    ) : (
                      <>
                        <div className={cn("break-words font-medium", f.kind === "money" && "num")}>
                          {show(value, f.kind, inv.currency) ?? <span className="font-normal italic text-ink-3">{ov?.unreadable ? "marked unreadable" : "not found on document"}</span>}
                        </div>
                        {ov && <div className="mt-0.5 text-[11.5px] text-accent">{ov.unreadable ? "Marked unreadable" : ov.confirmed ? "Confirmed" : "Corrected"} by {ov.by}{ov.reason ? ` — ${ov.reason}` : ""}
                          {!ov.unreadable && ex?.value && ex.value !== ov.value && <span className="text-ink-3"> (extracted: {show(ex.value, f.kind, inv.currency)})</span>}</div>}
                        {ex?.evidence?.snippet && !ov && <div className="mt-0.5 truncate font-mono text-[11px] text-ink-3" title={ex.evidence.snippet}>“{ex.evidence.snippet}”</div>}
                        {ex?.notes?.map((n) => <div key={n} className="mt-0.5 text-[11.5px] text-ink-3">{n}</div>)}
                      </>
                    )}
                  </td>
                  <td className="w-[210px] px-3 py-2 align-top">
                    <div className="flex items-center justify-end gap-1.5">
                      {value !== null && <Confidence value={conf} threshold={threshold} method={method} />}
                      {ex?.evidence && (
                        <button aria-label={`Show ${f.label} on document`} title="Show on document"
                          onClick={() => onEvidence({ page: ex.evidence!.page, bbox: ex.evidence!.bbox, label: f.label })}
                          className="rounded p-1 text-ink-3 hover:bg-surface-3 hover:text-accent"><Crosshair className="size-3.5" /></button>
                      )}
                      {canEdit && f.editable && editing !== f.key && (
                        <>
                          {low && <button title="Confirm value" aria-label={`Confirm ${f.label}`} className="rounded p-1 text-ink-3 hover:bg-surface-3 hover:text-success"
                            onClick={() => act({ action: "CONFIRM_FIELD", field: f.key }, `${f.label} confirmed; re-running checks`)}><Check className="size-3.5" /></button>}
                          <button title="Correct value" aria-label={`Correct ${f.label}`} className="rounded p-1 text-ink-3 hover:bg-surface-3 hover:text-ink"
                            onClick={() => { setEditing(f.key); setDraft(value ?? ""); }}><Pencil className="size-3.5" /></button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {issues.length > 0 && (
        <div className="space-y-1">
          <SectionTitle>Extraction issues</SectionTitle>
          {issues.map((i, n) => <p key={n} className="text-[12.5px] text-warning">{humanize(i.code)} · {i.message}</p>)}
        </div>
      )}
      <div>
        <SectionTitle className="mb-2">Line items as extracted</SectionTitle>
        <div className="overflow-hidden rounded-md border border-line">
          <Table>
            <THead><tr><SortTh label="#" field="no" {...lt} /><SortTh label="Description" field="desc" {...lt} />
              <SortTh label="Qty" field="qty" align="right" {...lt} /><SortTh label="Unit" field="unit" {...lt} />
              <SortTh label="Rate" field="rate" align="right" {...lt} /><SortTh label="GST %" field="gst" align="right" {...lt} />
              <SortTh label="Amount" field="amount" align="right" {...lt} /><SortTh label="Conf." field="conf" align="right" {...lt} /><Th /></tr></THead>
            <tbody>
              {(lt.rows ?? []).map((l) => (
                <tr key={l.id}>
                  <Td className="text-ink-3">{l.line_number}</Td>
                  <Td className="max-w-[280px]">{l.description}</Td>
                  <Td align="right">{qty(l.quantity)}</Td>
                  <Td className="text-ink-2">{l.unit ?? "—"}</Td>
                  <Td align="right">{money(l.unit_price, null)}</Td>
                  <Td align="right">{l.tax_rate ?? "—"}</Td>
                  <Td align="right">{money(l.line_subtotal, null)}</Td>
                  <Td align="right">{l.extraction_confidence ? <Confidence value={Number(l.extraction_confidence)} threshold={threshold} /> : "—"}</Td>
                  <Td>{l.evidence && <button aria-label="Show line on document" onClick={() => onEvidence({ page: l.evidence!.page, bbox: l.evidence!.bbox, label: `line ${l.line_number}` })}
                    className="rounded p-1 text-ink-3 hover:bg-surface-3 hover:text-accent"><Crosshair className="size-3.5" /></button>}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
          {inv.lines.length === 0 && <p className="p-4 text-center text-[13px] text-ink-3">No line items were extracted.</p>}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ reconciliation
type ReconRow = { invoice_line: number; description: string; matched: boolean; po_line?: number; po_description?: string;
  match_score?: number; quantity?: string; ordered?: string; previously_invoiced?: string; remaining_before?: string;
  received?: string; received_not_invoiced?: string; unit_price?: string; po_unit_price?: string; price_variance_pct?: string;
  tax_rate?: string; po_tax_rate?: string; line_subtotal?: string };

function cellTone(failed: boolean) { return failed ? "bg-danger-soft text-danger font-medium" : ""; }

export function ReconciliationPanel({ inv }: { inv: InvoiceDetail }) {
  const out = inv.latest_run?.stage_outputs?.FINANCIAL_RECONCILIATION as { match_mode: string | null; table: ReconRow[];
    summary: Record<string, unknown> } | undefined;
  const checks = inv.checks.filter((c) => c.stage === "FINANCIAL_RECONCILIATION");
  const n = (v: string | number | null | undefined) => (v === null || v === undefined || v === "" ? null : Number(String(v).replace(/[^\d.-]/g, "")));
  const rt = useClientSort(out?.table, {
    line: (r) => r.invoice_line, desc: (r) => r.description, qty: (r) => n(r.quantity), ordered: (r) => n(r.ordered),
    prev: (r) => n(r.previously_invoiced), remaining: (r) => n(r.remaining_before), received: (r) => n(r.received),
    rate: (r) => n(r.unit_price), porate: (r) => n(r.po_unit_price), var: (r) => n(r.price_variance_pct), gst: (r) => n(r.tax_rate),
  }, { sort: "line", order: "asc" });
  const mt = useClientSort(checks.filter((c) => c.expected || c.actual), {
    result: (c) => (c.status === "PASS" ? 1 : 0), check: (c) => c.name, subject: (c) => c.subject, actual: (c) => n(c.actual),
    expected: (c) => n(c.expected), delta: (c) => n(c.delta), tol: (c) => c.threshold,
  }, { sort: "result", order: "asc" });
  const failedFor = (code: string, line: number) => checks.some((c) => c.code === code && c.subject === `line ${line}` && c.status === "FAIL");
  if (!out) return <p className="p-6 text-center text-[13px] text-ink-3">Reconciliation has not run for this invoice{inv.status === "FAILED" ? " (processing failed before this stage)" : ""}.</p>;
  const s = out.summary as { po_number?: string; po_value?: string; previously_invoiced_value?: string; remaining_value_after?: string; grns?: string[]; po_type?: string };
  const threeWay = out.match_mode === "THREE_WAY";
  return (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={out.match_mode ? "accent" : "neutral"}>{out.match_mode === "THREE_WAY" ? "Three-way match: invoice · PO · goods receipt" :
          out.match_mode === "TWO_WAY" ? "Two-way match: invoice · PO" : "No PO matched: arithmetic checks only"}</Badge>
        {s.po_number && <span className="text-[12.5px] text-ink-2">against <span className="font-mono">{s.po_number}</span> ({s.po_type?.toLowerCase()})</span>}
        {s.grns && s.grns.length > 0 && <span className="text-[12.5px] text-ink-3">receipts: <span className="font-mono">{s.grns.join(", ")}</span></span>}
        {!threeWay && s.po_type === "SERVICES" && <span className="text-[12px] text-ink-3">Services PO: no goods receipt applies.</span>}
      </div>
      {s.po_value && (
        <div className="grid grid-cols-2 gap-3 rounded-md border border-line bg-surface-2 p-3 sm:grid-cols-4">
          <div><div className="text-[11.5px] text-ink-3">PO value (pre-tax)</div><div className="num font-medium">{money(s.po_value)}</div></div>
          <div><div className="text-[11.5px] text-ink-3">Previously invoiced</div><div className="num font-medium">{money(s.previously_invoiced_value)}</div></div>
          <div><div className="text-[11.5px] text-ink-3">This invoice</div><div className="num font-medium">{money(inv.subtotal)}</div></div>
          <div><div className="text-[11.5px] text-ink-3">Remaining after</div><div className={cn("num font-medium", Number(s.remaining_value_after) < 0 && "text-danger")}>{money(s.remaining_value_after)}</div></div>
        </div>
      )}
      {out.table.length > 0 && (
        <div className="overflow-hidden rounded-md border border-line">
          <Table>
            <THead><tr>
              <SortTh label="Line" field="line" {...rt} /><SortTh label="Invoice ↔ PO description" field="desc" {...rt} />
              <SortTh label="Inv qty" field="qty" align="right" {...rt} /><SortTh label="Ordered" field="ordered" align="right" {...rt} />
              <SortTh label="Prev. invoiced" field="prev" align="right" {...rt} /><SortTh label="Remaining" field="remaining" align="right" {...rt} />
              {threeWay && <SortTh label="Received" field="received" align="right" {...rt} />}
              <SortTh label="Inv rate" field="rate" align="right" {...rt} /><SortTh label="PO rate" field="porate" align="right" {...rt} />
              <SortTh label="Var." field="var" align="right" {...rt} /><SortTh label="GST" field="gst" align="right" {...rt} />
            </tr></THead>
            <tbody>
              {(rt.rows ?? []).map((r) => (
                <tr key={r.invoice_line}>
                  <Td className="whitespace-nowrap text-ink-3">{r.invoice_line}{r.matched ? ` → ${r.po_line}` : ""}</Td>
                  <Td className="max-w-[260px]">
                    <div className="truncate" title={r.description}>{r.description}</div>
                    {r.matched ? <div className="truncate text-[11.5px] text-ink-3" title={r.po_description}>PO: {r.po_description} · match {Number(r.match_score).toFixed(2)}</div>
                      : <Badge tone="danger" className="mt-0.5 h-5 text-[11px]">No matching PO line</Badge>}
                  </Td>
                  <Td align="right" className={cellTone(failedFor("QUANTITY_EXCEEDED", r.invoice_line) || failedFor("GRN_QUANTITY_MISMATCH", r.invoice_line))}>{qty(r.quantity)}</Td>
                  <Td align="right">{qty(r.ordered)}</Td>
                  <Td align="right">{qty(r.previously_invoiced)}</Td>
                  <Td align="right">{qty(r.remaining_before)}</Td>
                  {threeWay && <Td align="right">{qty(r.received)}</Td>}
                  <Td align="right" className={cellTone(failedFor("PRICE_VARIANCE_EXCEEDED", r.invoice_line))}>{money(r.unit_price, null)}</Td>
                  <Td align="right">{money(r.po_unit_price, null)}</Td>
                  <Td align="right" className={cellTone(failedFor("PRICE_VARIANCE_EXCEEDED", r.invoice_line))}>{r.price_variance_pct ? `${Number(r.price_variance_pct) > 0 ? "+" : ""}${r.price_variance_pct}%` : "—"}</Td>
                  <Td align="right" className={cellTone(failedFor("TAX_MISMATCH", r.invoice_line))}>{r.tax_rate ?? "—"}{r.po_tax_rate ? ` / ${Number(r.po_tax_rate)}` : ""}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
      <div>
        <SectionTitle className="mb-2">Measured checks</SectionTitle>
        <div className="overflow-hidden rounded-md border border-line">
          <Table>
            <THead><tr><SortTh label="Result" field="result" {...mt} /><SortTh label="Check" field="check" {...mt} />
              <SortTh label="Subject" field="subject" {...mt} /><SortTh label="Actual" field="actual" align="right" {...mt} />
              <SortTh label="Expected" field="expected" align="right" {...mt} /><SortTh label="Delta" field="delta" align="right" {...mt} />
              <SortTh label="Tolerance" field="tol" align="right" {...mt} /></tr></THead>
            <tbody>
              {(mt.rows ?? []).map((c) => (
                <tr key={c.id} className={cn(c.status !== "PASS" && c.outcome !== "NONE" && "bg-danger-soft/40")}>
                  <Td><CheckIcon status={c.status} outcome={c.outcome} /></Td>
                  <Td className="text-[12.5px]" title={c.message}>{c.name}</Td>
                  <Td className="text-[12.5px] text-ink-2">{c.subject ?? "—"}</Td>
                  <Td align="right">{c.actual ?? "—"}</Td>
                  <Td align="right" className="text-ink-2">{c.expected ?? "—"}</Td>
                  <Td align="right" className={cn(c.status === "FAIL" && "font-medium text-danger")}>{c.delta ?? "—"}</Td>
                  <Td align="right" className="text-ink-3">{c.threshold ?? "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ checks
export function ChecksPanel({ inv }: { inv: InvoiceDetail }) {
  const order = STAGES.map((s) => s.key);
  const byStage = [...new Set(inv.checks.map((c) => c.stage))].sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const failing = inv.checks.filter((c) => c.status !== "PASS" && c.outcome !== "NONE");
  if (!inv.checks.length) return <p className="p-6 text-center text-[13px] text-ink-3">No checks recorded yet.</p>;
  return (
    <div className="space-y-4 p-4">
      <p className="text-[12.5px] text-ink-3">{inv.checks.length} checks from run #{inv.latest_run?.attempt} under policy v{inv.checks[0]?.policy_version} ·
        <span className="text-ink"> {failing.length} affecting the decision</span></p>
      {byStage.map((stage) => {
        const list = inv.checks.filter((c) => c.stage === stage).sort((a, b) => Number(a.status === "PASS") - Number(b.status === "PASS"));
        return (
          <div key={stage}>
            <SectionTitle className="mb-1.5">{STAGE_LABEL[stage] ?? stage}</SectionTitle>
            <ul className="divide-y divide-line overflow-hidden rounded-md border border-line">
              {list.map((c) => <CheckRow key={c.id} c={c} />)}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

function CheckRow({ c }: { c: CheckT }) {
  const fail = c.status !== "PASS" && c.outcome !== "NONE";
  return (
    <li className={cn("flex gap-2.5 px-3 py-2", fail && "bg-surface-2")}>
      <CheckIcon status={c.status} outcome={c.outcome} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[13px] font-medium">{c.name}</span>
          {c.subject && <span className="text-[12px] text-ink-3">· {c.subject}</span>}
          {c.status !== "PASS" && <SeverityBadge severity={c.severity} />}
          {fail && c.outcome !== "REVIEW" && <Badge tone={c.outcome === "REJECT" ? "danger" : "warning"} className="h-5 text-[10.5px] uppercase">{c.outcome === "REJECT" ? "rejects" : "holds"}</Badge>}
          {c.accepted && <Badge tone="accent" className="h-5 text-[10.5px]">accepted by reviewer</Badge>}
          <span className="ml-auto font-mono text-[10.5px] text-ink-3">{c.code}</span>
        </div>
        <p className="mt-0.5 text-[12.5px] text-ink-2">{c.message}</p>
        {fail && c.resolution && <p className="mt-0.5 text-[11.5px] text-ink-3">Resolution: {{ ACCEPT: "a reviewer may accept with a reason",
          CORRECT: "fix the data (correct a field, select PO/vendor) or obtain the missing dependency",
          OVERRIDE: "AP manager override with a recorded reason", NONE: "wait for the dependency" }[c.resolution]}</p>}
      </div>
    </li>
  );
}

// ------------------------------------------------------------------------------------------------ matching
type Cand = { po_id: string; po_number: string; score: number; description: number; structure: number; price: number;
  amount: number; date: number; remaining_value: string; po_date: string; lines_matched: string };

export function MatchingPanel({ inv, onRun }: { inv: InvoiceDetail; onRun: (id: string) => void }) {
  const act = useAct(inv, onRun);
  const vr = inv.latest_run?.stage_outputs?.VENDOR_RESOLUTION as { status: string; method: string; score: number;
    candidates: { vendor_id: string; vendor_code: string; name: string; score: number; status: string }[];
    supporting: string[]; conflicting: string[] } | undefined;
  const pm = inv.latest_run?.stage_outputs?.PO_MATCHING as { status: string; method: string; po_number: string | null;
    candidates: Cand[]; notes: string[] } | undefined;
  const canAct = inv.permissions.can_act && OPEN.includes(inv.status);
  const { data: vendors } = useVendors({});
  const [vendorPick, setVendorPick] = React.useState("");
  return (
    <div className="space-y-4 p-4">
      <Card>
        <CardHeader title="Vendor resolution" description="Order: tax ID → vendor code → exact name/alias → fuzzy (candidates only)"
          action={vr && <Badge tone={vr.status === "RESOLVED" ? "success" : "warning"}>{humanize(vr.status)}{vr.method ? ` · ${vr.method}` : ""}</Badge>} />
        <div className="space-y-2 p-4 text-[12.5px]">
          {!vr && <p className="text-ink-3">Not run.</p>}
          {vr?.supporting.map((s) => <p key={s} className="text-success">✓ {s}</p>)}
          {vr?.conflicting.map((s) => <p key={s} className="text-warning">! {s}</p>)}
          {vr && vr.candidates.length > 0 && (
            <Table><THead><tr><Th>Candidate</Th><Th>Status</Th><Th align="right">Name similarity</Th></tr></THead>
              <tbody>{vr.candidates.map((c) => <tr key={c.vendor_id}><Td><span className="font-mono text-[11.5px] text-ink-3">{c.vendor_code}</span> {c.name}</Td>
                <Td>{humanize(c.status)}</Td><Td align="right">{c.score.toFixed(2)}</Td></tr>)}</tbody></Table>
          )}
          {canAct && vr && vr.status !== "RESOLVED" && (
            <form className="flex gap-2 pt-1" onSubmit={(e) => { e.preventDefault(); if (vendorPick) act({ action: "SELECT_VENDOR", vendor_id: vendorPick }, "Vendor selected; re-running checks"); }}>
              <select className="h-8 flex-1 rounded-md border border-line-strong bg-surface px-2 text-[13px]" value={vendorPick} onChange={(e) => setVendorPick(e.target.value)} aria-label="Select vendor">
                <option value="">Select the correct vendor…</option>
                {vendors?.items.map((v) => <option key={v.id} value={v.id}>{v.vendor_code} · {v.legal_name}</option>)}
              </select>
              <Button size="sm" variant="primary" type="submit" disabled={!vendorPick}>Use vendor</Button>
            </form>
          )}
        </div>
      </Card>
      <Card>
        <CardHeader title="Purchase order matching" description="Similarity ranks candidates; it never proves validity — reconciliation still runs"
          action={pm && <Badge tone={pm.status === "MATCHED" ? "success" : "warning"}>{humanize(pm.status)}{pm.method ? ` · ${pm.method}` : ""}</Badge>} />
        <div className="space-y-2 p-4 text-[12.5px]">
          {pm?.notes.map((n) => <p key={n} className="text-ink-2">{n}</p>)}
          {inv.po_selected_by_human && <p className="text-accent">PO chosen by a reviewer.</p>}
          {pm && pm.candidates.length > 0 && (
            <Table>
              <THead><tr><Th>PO</Th><Th align="right">Score</Th><Th align="right">Desc.</Th><Th align="right">Lines</Th>
                <Th align="right">Price</Th><Th align="right">Amount</Th><Th align="right">Date</Th><Th align="right">Remaining</Th>{canAct && <Th />}</tr></THead>
              <tbody>{pm.candidates.map((c) => (
                <tr key={c.po_id}>
                  <Td><Link className="font-mono text-accent hover:underline" href={`/purchase-orders/${c.po_id}`}>{c.po_number}</Link>
                    <div className="text-[11px] text-ink-3">{date(c.po_date)}</div></Td>
                  <Td align="right" className="font-medium">{c.score.toFixed(2)}</Td>
                  <Td align="right">{c.description.toFixed(2)}</Td><Td align="right">{c.lines_matched}</Td>
                  <Td align="right">{c.price.toFixed(2)}</Td><Td align="right">{c.amount.toFixed(2)}</Td><Td align="right">{c.date.toFixed(1)}</Td>
                  <Td align="right">{money(c.remaining_value, null)}</Td>
                  {canAct && <Td><Button size="sm" onClick={() => act({ action: "SELECT_PO", po_id: c.po_id, reason: "Selected from ranked candidates" }, `${c.po_number} selected; re-running checks`)}>Select</Button></Td>}
                </tr>))}</tbody>
            </Table>
          )}
          {pm && pm.candidates.length > 1 && <p className="text-[11.5px] text-ink-3">Score = 0.35 description + 0.25 line structure + 0.20 price within tolerance + 0.10 amount fits remaining + 0.10 date within validity. Auto-select needs ≥ threshold and a clear margin over the runner-up.</p>}
        </div>
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ activity
export function ActivityPanel({ inv }: { inv: InvoiceDetail }) {
  const { data: audit, refetch } = useInvoiceAudit(inv.id);
  const [note, setNote] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  async function addNote(e: React.FormEvent) {
    e.preventDefault();
    if (!note.trim()) return;
    setBusy(true);
    try { await api.post(`/invoices/${inv.id}/notes`, { body: note }); setNote(""); refetch(); toast.success("Note added"); }
    catch (err) { toast.error(err instanceof ApiError ? err.message : "Could not add note"); }
    finally { setBusy(false); }
  }
  return (
    <div className="space-y-5 p-4">
      {inv.info_request_draft && (
        <div>
          <div className="mb-1.5 flex items-center justify-between"><SectionTitle>Vendor information request (draft, not sent)</SectionTitle>
            <Button size="sm" variant="ghost" onClick={() => { navigator.clipboard.writeText(inv.info_request_draft!); toast.success("Draft copied"); }}><Copy className="size-3.5" />Copy</Button></div>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-surface-2 p-3 text-[12px] leading-relaxed text-ink-2">{inv.info_request_draft}</pre>
        </div>
      )}
      <div>
        <SectionTitle className="mb-1.5">Internal notes</SectionTitle>
        {inv.permissions.can_act && (
          <form onSubmit={addNote} className="mb-2 flex gap-2">
            <Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add an internal note (visible to the AP team, recorded in the audit log)" />
            <Button type="submit" loading={busy} disabled={!note.trim()} aria-label="Add note"><Send className="size-3.5" /></Button>
          </form>
        )}
        {inv.notes.length === 0 ? <p className="text-[12.5px] text-ink-3">No notes.</p> : (
          <ul className="space-y-2">{inv.notes.map((n) => (
            <li key={n.id} className="rounded-md border border-line px-3 py-2"><div className="text-[12px] text-ink-3">{n.author.name} · {ago(n.created_at)}</div>
              <p className="mt-0.5 whitespace-pre-wrap text-[13px]">{n.body}</p></li>))}</ul>
        )}
      </div>
      <div>
        <SectionTitle className="mb-1.5">Processing runs</SectionTitle>
        <ul className="divide-y divide-line overflow-hidden rounded-md border border-line">
          {inv.runs.map((r) => (
            <li key={r.id}><Link href={`/runs/${r.id}`} className="flex items-center gap-3 px-3 py-2 hover:bg-surface-2">
              <span className="font-medium">#{r.attempt}</span><span className="text-[12.5px] text-ink-2">{humanize(r.trigger)} by {r.triggered_by}</span>
              <RunStatusBadge status={r.status} />{r.decision && <StatusBadge status={r.decision} />}
              <span className="ml-auto num text-[12px] text-ink-3">{ms(r.duration_ms)} · {ago(r.created_at)}</span></Link></li>
          ))}
        </ul>
      </div>
      <div>
        <SectionTitle className="mb-1.5">Audit trail</SectionTitle>
        <ol className="relative space-y-3 border-l border-line pl-4">
          {(audit ?? []).map((a) => (
            <li key={a.id} className="relative">
              <span className={cn("absolute -left-[22px] top-0.5 flex size-[13px] items-center justify-center rounded-full ring-2 ring-surface",
                a.actor_type === "USER" ? "bg-accent" : "bg-ink-3")} />
              <div className="flex flex-wrap items-center gap-1.5 text-[12.5px]">
                <Badge tone={a.actor_type === "USER" ? "accent" : "neutral"} className="h-5 text-[11px]" icon={a.actor_type === "USER" ? <UserIcon /> : <Cpu />}>
                  {a.actor_type === "USER" ? "Human" : "System"}</Badge>
                <span className="font-medium">{humanize(a.action)}</span>
                <span className="text-ink-3">· {a.actor_name}</span>
                <span className="ml-auto text-[11.5px] text-ink-3">{dateTime(a.occurred_at)}</span>
              </div>
              {a.note && <p className="mt-0.5 text-[12.5px] text-ink-2">{a.note}</p>}
              {a.before && a.after && "status" in a.before && "status" in a.after && a.before.status !== a.after.status &&
                <p className="mt-0.5 text-[11.5px] text-ink-3">{humanize(String(a.before.status))} → {humanize(String(a.after.status))}</p>}
              {a.after && "field" in a.after && <p className="mt-0.5 text-[11.5px] text-ink-3">{String(a.after.field)}: {String(a.before?.value ?? "—")} → {String(a.after.value ?? "unreadable")}</p>}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
