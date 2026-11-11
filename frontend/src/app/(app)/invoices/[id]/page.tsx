"use client";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { AlertTriangle, Ban, CheckCircle2, Copy, FileText, Hand, Loader2, Mail, MoreHorizontal, Play, RefreshCw, ShieldAlert,
  UserPlus } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { ActivityPanel, ChecksPanel, FieldsPanel, MatchingPanel, ReconciliationPanel } from "@/components/invoice/panels";
import { PageHeader } from "@/components/layout/shell";
import type { Highlight } from "@/components/pdf/pdf-viewer";
import { PriorityMark, ReasonChip, StatusBadge, useReasonTitle } from "@/components/status/status";
import { Button } from "@/components/ui/button";
import { Dialog, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/overlays";
import { Card, ErrorState, Kv, Label, Skeleton, Textarea } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api/client";
import { useDemoUsers, useInvoice, usePolicies, useReviewAction } from "@/lib/api/hooks";
import type { InvoiceDetail } from "@/lib/api/types";
import { bytes, date, dateTime, humanize, money } from "@/lib/format";
import { cn } from "@/lib/utils";

const PdfViewer = dynamic(() => import("@/components/pdf/pdf-viewer"), { ssr: false,
  loading: () => <div className="lf-pulse h-full bg-surface-3" /> });

type ActionKind = "MARK_READY" | "APPROVE" | "HOLD" | "REJECT" | "REQUEST_INFO" | "RE_EVALUATE" | "CANCEL";

const RESOLUTION_NOTE: Record<string, string> = {
  ACCEPT: "Reviewer may accept with a reason", OVERRIDE: "AP manager override (audited)",
  CORRECT: "Must be fixed — correct data or select PO/vendor", NONE: "Waits for a dependency",
};

function DecisionBanner({ inv }: { inv: InvoiceDetail }) {
  const tone = inv.status === "READY_FOR_APPROVAL" || inv.status === "APPROVED" ? "success" :
    inv.status === "REJECTED" ? "danger" : inv.status === "FAILED" || inv.status === "CANCELLED" ? "neutral" :
      inv.status === "PROCESSING" ? "accent" : "warning";
  const Icon = { success: CheckCircle2, danger: Ban, neutral: AlertTriangle, accent: Loader2, warning: AlertTriangle }[tone];
  const security = inv.reason_codes.includes("VENDOR_BANK_DETAILS_CHANGED");
  return (
    <Card className={cn("mb-4 border-l-[3px]", { success: "border-l-success", danger: "border-l-danger", neutral: "border-l-ink-3",
      accent: "border-l-accent", warning: "border-l-warning" }[tone])}>
      <div className="flex flex-wrap items-start gap-3 px-4 py-3">
        <Icon className={cn("mt-0.5 size-5 shrink-0", { success: "text-success", danger: "text-danger", neutral: "text-ink-3",
          accent: "animate-spin text-accent", warning: "text-warning" }[tone])} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={inv.status} />
            <span className="text-[12px] text-ink-3">{inv.status === "PROCESSING" ? "Processing run in progress" :
              `Decided by ${inv.decided_by === "HUMAN" ? "a person" : "the decision engine"}${inv.decided_at ? ` · ${dateTime(inv.decided_at)}` : ""}`}</span>
            {security && <span className="inline-flex items-center gap-1 rounded bg-danger-soft px-1.5 py-0.5 text-[11.5px] font-medium text-danger"><ShieldAlert className="size-3.5" />Security escalation</span>}
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-ink">{inv.decision_summary ?? "Awaiting decision."}</p>
          {inv.reason_codes.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{inv.reason_codes.map((c) => <ReasonChip key={c} code={c} />)}</div>}
        </div>
        {inv.next_action && (
          <div className="w-full rounded-md border border-line bg-surface-2 px-3 py-2 text-[12.5px] sm:w-auto sm:max-w-[320px]">
            <div className="text-[11px] font-medium uppercase tracking-wide text-ink-3">Next action</div>
            <div className="mt-0.5 text-ink">{inv.next_action}</div>
          </div>
        )}
      </div>
      {inv.duplicate_of && (
        <div className="border-t border-line bg-warning-soft/50 px-4 py-2 text-[12.5px]">
          Possible duplicate of <Link className="font-medium text-accent hover:underline" href={`/invoices/${inv.duplicate_of.id}`}>{inv.duplicate_of.reference}</Link> ({humanize(inv.duplicate_of.status)}). The original record is untouched.
        </div>
      )}
      {inv.duplicate_submissions.length > 0 && (
        <div className="flex items-center gap-2 border-t border-line px-4 py-2 text-[12.5px] text-ink-2"><Copy className="size-3.5 text-ink-3" />
          Identical file re-submitted {inv.duplicate_submissions.length}× (latest: “{inv.duplicate_submissions[0].filename}” by {inv.duplicate_submissions[0].by}). No new invoice was created.
        </div>
      )}
    </Card>
  );
}

function ActionDialog({ inv, kind, onClose, onRun }: { inv: InvoiceDetail; kind: ActionKind | null; onClose: () => void;
  onRun: (id: string) => void }) {
  const m = useReviewAction(inv.id);
  const [reason, setReason] = React.useState("");
  const [draft, setDraft] = React.useState<string | null>(null);
  const title = useReasonTitle();
  React.useEffect(() => { setReason(""); setDraft(null); }, [kind]);
  if (!kind) return null;
  const failing = inv.checks.filter((c) => c.status !== "PASS" && c.outcome !== "NONE");
  const mustFix = failing.filter((c) => c.resolution === "CORRECT" || c.resolution === "NONE");
  const overrides = failing.filter((c) => c.resolution === "OVERRIDE");
  const managerOnly = kind === "MARK_READY" && overrides.length > 0 && !inv.permissions.is_manager;
  const needsReason = ["HOLD", "REJECT", "CANCEL"].includes(kind) || (kind === "MARK_READY" && failing.length > 0);
  const blocked = (kind === "MARK_READY" && mustFix.length > 0) || managerOnly;
  const meta: Record<ActionKind, { title: string; desc: string; cta: string; variant: "primary" | "danger" | "secondary" }> = {
    MARK_READY: { title: "Mark ready for approval", desc: "Accept the open exceptions with a recorded reason. A second person must still approve.", cta: "Accept and mark ready", variant: "primary" },
    APPROVE: { title: "Approve invoice", desc: "Approval authorises inclusion in a payment run. LedgerFlow does not execute payments.", cta: "Approve", variant: "primary" },
    HOLD: { title: "Place on hold", desc: "The invoice stays unpaid until released. Any PO reservation is released.", cta: "Place on hold", variant: "secondary" },
    REJECT: { title: "Reject invoice", desc: "Rejection is a business decision and is recorded with your reason.", cta: "Reject", variant: "danger" },
    REQUEST_INFO: { title: "Request information from vendor", desc: "LedgerFlow drafts the message from the open exceptions. It is never sent automatically.", cta: "Prepare draft", variant: "primary" },
    RE_EVALUATE: { title: "Re-run deterministic checks", desc: "Re-runs vendor, PO, reconciliation, duplicate and policy stages with current master data (e.g. after a GRN is posted). Extraction is not repeated.", cta: "Re-run checks", variant: "primary" },
    CANCEL: { title: "Cancel invoice", desc: "Manager-only. Use for invoices withdrawn by the vendor or uploaded in error.", cta: "Cancel invoice", variant: "danger" },
  };
  const cfg = meta[kind];

  async function submit() {
    try {
      const r = await m.mutateAsync({ action: kind!, reason: reason.trim() || undefined });
      if (kind === "REQUEST_INFO" && r.draft) { setDraft(r.draft); toast.success("Draft prepared. Invoice placed on hold."); return; }
      toast.success(r.message);
      onClose();
      if (r.run_id) onRun(r.run_id);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Action failed");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()} title={cfg.title} description={cfg.desc} wide={kind === "MARK_READY" || !!draft}
      footer={draft ? <><Button onClick={() => { navigator.clipboard.writeText(draft); toast.success("Copied"); }}><Copy />Copy draft</Button><Button variant="primary" onClick={onClose}>Done</Button></> :
        <><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant={cfg.variant} onClick={submit} loading={m.isPending} disabled={blocked || (needsReason && !reason.trim())}>{cfg.cta}</Button></>}>
      {draft ? (
        <pre className="whitespace-pre-wrap rounded-md border border-line bg-surface-2 p-3 text-[12.5px] leading-relaxed">{draft}</pre>
      ) : (
        <div className="space-y-3">
          {kind === "MARK_READY" && failing.length > 0 && (
            <ul className="divide-y divide-line overflow-hidden rounded-md border border-line">
              {failing.map((c) => (
                <li key={c.id} className="flex items-start justify-between gap-3 px-3 py-2 text-[12.5px]">
                  <div><div className="font-medium">{title(c.code)}{c.subject ? ` · ${c.subject}` : ""}</div><div className="text-ink-3">{c.message}</div></div>
                  <span className={cn("shrink-0 text-[11.5px]", c.resolution === "CORRECT" || c.resolution === "NONE" ? "text-danger" : c.resolution === "OVERRIDE" ? "text-warning" : "text-ink-2")}>
                    {RESOLUTION_NOTE[c.resolution ?? "ACCEPT"]}</span>
                </li>
              ))}
            </ul>
          )}
          {kind === "MARK_READY" && mustFix.length > 0 && <p className="rounded-md bg-danger-soft px-3 py-2 text-[12.5px] text-danger">Some exceptions cannot be accepted: correct the data, select the PO/vendor, or wait for the dependency first.</p>}
          {managerOnly && <p className="rounded-md bg-warning-soft px-3 py-2 text-[12.5px] text-warning">Blocker-level exceptions require an AP manager override.</p>}
          {kind === "APPROVE" && <p className="text-[12.5px] text-ink-2">Value {money(inv.grand_total, inv.currency)} · {inv.vendor?.legal_name}. The person who accepted exceptions cannot also approve (separation of duties).</p>}
          {(needsReason || kind === "APPROVE" || kind === "REQUEST_INFO" || kind === "RE_EVALUATE") && (
            <div>
              <Label htmlFor="reason">{needsReason ? "Reason (required, recorded in the audit log)" : "Note (optional)"}</Label>
              <Textarea id="reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus
                placeholder={kind === "MARK_READY" ? "e.g. Price revision agreed by the buyer on 6 Nov; PO amendment raised" : ""} />
            </div>
          )}
        </div>
      )}
    </Dialog>
  );
}

function AssignMenu({ inv }: { inv: InvoiceDetail }) {
  const { data: users } = useDemoUsers();
  const [busy, setBusy] = React.useState(false);
  const { refetch } = useInvoice(inv.id);
  async function assign(id: string | null) {
    setBusy(true);
    try { await api.post(`/invoices/${inv.id}/assign`, { assignee_id: id }); toast.success("Assignment updated"); refetch(); }
    catch (e) { toast.error(e instanceof ApiError ? e.message : "Could not assign"); } finally { setBusy(false); }
  }
  return (
    <Dropdown.Root>
      <Dropdown.Trigger asChild><Button disabled={busy}><UserPlus />{inv.assignee ? inv.assignee.name : "Assign"}</Button></Dropdown.Trigger>
      <Dropdown.Portal><Dropdown.Content align="end" sideOffset={6} className="z-50 min-w-52 rounded-md border border-line bg-surface p-1 shadow-lg">
        {(users ?? []).filter((u) => u.role !== "AUDITOR").map((u) => (
          <Dropdown.Item key={u.id} onSelect={() => assign(u.id)} className="cursor-pointer rounded px-2 py-1.5 text-[13px] outline-none data-[highlighted]:bg-surface-3">
            {u.name} <span className="text-ink-3">· {u.title}</span></Dropdown.Item>))}
        {inv.assignee && <Dropdown.Item onSelect={() => assign(null)} className="cursor-pointer rounded px-2 py-1.5 text-[13px] text-ink-3 outline-none data-[highlighted]:bg-surface-3">Unassign</Dropdown.Item>}
      </Dropdown.Content></Dropdown.Portal>
    </Dropdown.Root>
  );
}

export default function InvoicePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: inv, error, refetch } = useInvoice(id);
  const { data: policies } = usePolicies();
  const [highlight, setHighlight] = React.useState<Highlight>(null);
  const [dialog, setDialog] = React.useState<ActionKind | null>(null);
  const [tab, setTab] = React.useState("fields");
  const onRun = (runId: string) => router.push(`/runs/${runId}`);

  React.useEffect(() => {
    if (inv && inv.status !== "PROCESSING" && inv.checks.some((c) => c.stage === "FINANCIAL_RECONCILIATION" && c.status === "FAIL" && c.outcome !== "NONE")
      && !inv.checks.some((c) => ["FIELD_EXTRACTION", "RISK_AND_POLICY_CHECKS"].includes(c.stage) && c.code.includes("CONFIDENCE") && c.status === "FAIL"))
      setTab((t) => (t === "fields" ? "recon" : t));
    // only on first load of a given invoice
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inv?.id]);

  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (!inv) return <div className="space-y-3"><Skeleton className="h-12 w-96" /><Skeleton className="h-24" /><Skeleton className="h-[600px]" /></div>;

  const threshold = Number(policies?.find((p) => p.is_active)?.settings.critical_field_confidence ?? 0.85);
  const can = inv.permissions.can_act;
  const s = inv.status;
  const failingCount = inv.checks.filter((c) => c.status !== "PASS" && c.outcome !== "NONE").length;
  const latestRun = inv.latest_run;

  return (
    <div className="mx-auto max-w-[1600px]">
      <PageHeader
        crumbs={[{ href: "/invoices", label: "Invoices" }, { label: inv.reference }]}
        title={<span className="flex flex-wrap items-center gap-2.5">{inv.invoice_number ?? inv.reference}
          <span className="text-[14px] font-normal text-ink-3">{inv.vendor?.legal_name ?? inv.vendor_name_raw ?? "Vendor unresolved"}</span></span>}
        description={<span className="num">{inv.reference} · {money(inv.grand_total, inv.currency)} · invoice date {date(inv.invoice_date)} · received {dateTime(inv.created_at)}{inv.uploaded_by ? ` by ${inv.uploaded_by}` : ""}</span>}
        actions={<>
          <PriorityMark priority={inv.priority} />
          {can && <AssignMenu inv={inv} />}
          {can && ["NEEDS_REVIEW", "ON_HOLD"].includes(s) && <>
            <Button onClick={() => setDialog("REQUEST_INFO")}><Mail />Request info</Button>
            {s === "NEEDS_REVIEW" && <Button onClick={() => setDialog("HOLD")}><Hand />Hold</Button>}
            <Button variant="danger" onClick={() => setDialog("REJECT")}><Ban />Reject</Button>
            <Button variant="primary" onClick={() => setDialog("MARK_READY")}><CheckCircle2 />Mark ready</Button>
          </>}
          {can && s === "READY_FOR_APPROVAL" && <>
            <Button onClick={() => setDialog("HOLD")}><Hand />Hold</Button>
            <Button variant="danger" onClick={() => setDialog("REJECT")}><Ban />Reject</Button>
            <Button variant="primary" onClick={() => setDialog("APPROVE")}><CheckCircle2 />Approve</Button>
          </>}
          {s === "FAILED" && latestRun && <Button variant="primary" asChild><Link href={`/runs/${latestRun.id}`}><RefreshCw />Run details & retry</Link></Button>}
          {s === "PROCESSING" && latestRun && <Button variant="primary" asChild><Link href={`/runs/${latestRun.id}`}><Play />Watch live run</Link></Button>}
          <Dropdown.Root>
            <Dropdown.Trigger asChild><Button size="icon" aria-label="More actions"><MoreHorizontal /></Button></Dropdown.Trigger>
            <Dropdown.Portal><Dropdown.Content align="end" sideOffset={6} className="z-50 min-w-56 rounded-md border border-line bg-surface p-1 shadow-lg">
              <Dropdown.Item asChild className="cursor-pointer rounded px-2 py-1.5 text-[13px] outline-none data-[highlighted]:bg-surface-3">
                <a href={`/api/invoices/${inv.id}/report`} target="_blank" rel="noreferrer">Decision report (printable)</a></Dropdown.Item>
              <Dropdown.Item asChild className="cursor-pointer rounded px-2 py-1.5 text-[13px] outline-none data-[highlighted]:bg-surface-3">
                <a href={`/api/invoices/${inv.id}/document`} target="_blank" rel="noreferrer">Original PDF</a></Dropdown.Item>
              {can && ["NEEDS_REVIEW", "ON_HOLD", "READY_FOR_APPROVAL"].includes(s) &&
                <Dropdown.Item onSelect={() => setDialog("RE_EVALUATE")} className="cursor-pointer rounded px-2 py-1.5 text-[13px] outline-none data-[highlighted]:bg-surface-3">Re-run checks</Dropdown.Item>}
              {inv.permissions.is_manager && ["NEEDS_REVIEW", "ON_HOLD", "READY_FOR_APPROVAL", "FAILED"].includes(s) &&
                <Dropdown.Item onSelect={() => setDialog("CANCEL")} className="cursor-pointer rounded px-2 py-1.5 text-[13px] text-danger outline-none data-[highlighted]:bg-surface-3">Cancel invoice…</Dropdown.Item>}
            </Dropdown.Content></Dropdown.Portal>
          </Dropdown.Root>
        </>}
      />
      <DecisionBanner inv={inv} />

      <div className="grid gap-4 xl:grid-cols-[minmax(420px,0.9fr)_minmax(0,1.1fr)]">
        <Card className="overflow-hidden xl:sticky xl:top-16 xl:h-[calc(100vh-84px)]">
          <div className="flex h-[70vh] flex-col xl:h-full">
            <div className="flex items-center gap-2 border-b border-line px-3 py-2 text-[12px] text-ink-2">
              <FileText className="size-3.5 text-ink-3" /><span className="truncate font-medium text-ink">{inv.original_filename}</span>
              <span className="text-ink-3">· {bytes(inv.file_size)} · {inv.page_count ?? "?"} page(s)</span>
              <span className="ml-auto truncate font-mono text-[11px] text-ink-3" title={inv.file_sha256}>sha256 {inv.file_sha256.slice(0, 12)}…</span>
            </div>
            <PdfViewer url={`/api/invoices/${inv.id}/document`} highlight={highlight} className="min-h-0 flex-1" />
          </div>
        </Card>

        <Card className="min-w-0">
          <dl className="grid grid-cols-2 gap-3 border-b border-line px-4 py-3 sm:grid-cols-4">
            <Kv label="Vendor">{inv.vendor ? <Link className="text-accent hover:underline" href={`/vendors/${inv.vendor.id}`}>{inv.vendor.vendor_code}</Link> : <span className="text-warning">Unresolved</span>}</Kv>
            <Kv label="PO">{inv.po_id ? <Link className="font-mono text-accent hover:underline" href={`/purchase-orders/${inv.po_id}`}>{inv.po_number}</Link> : <span className="text-warning">{inv.po_reference_raw ?? "None matched"}</span>}</Kv>
            <Kv label="Match">{inv.match_mode ? humanize(inv.match_mode) : "—"}</Kv>
            <Kv label="Run / policy">{latestRun ? <Link className="text-accent hover:underline" href={`/runs/${latestRun.id}`}>#{latestRun.attempt} · v{latestRun.policy_version ?? "—"}</Link> : "—"}</Kv>
          </dl>
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="overflow-x-auto">
              <TabsTrigger value="fields">Extracted data</TabsTrigger>
              <TabsTrigger value="recon">Reconciliation</TabsTrigger>
              <TabsTrigger value="checks">Checks {failingCount > 0 && <span className="num rounded bg-warning-soft px-1 text-[11px] text-warning">{failingCount}</span>}</TabsTrigger>
              <TabsTrigger value="matching">Vendor & PO</TabsTrigger>
              <TabsTrigger value="activity">Activity & audit</TabsTrigger>
            </TabsList>
            <TabsContent value="fields"><FieldsPanel inv={inv} threshold={threshold} onEvidence={setHighlight} onRun={onRun} /></TabsContent>
            <TabsContent value="recon"><ReconciliationPanel inv={inv} /></TabsContent>
            <TabsContent value="checks"><ChecksPanel inv={inv} /></TabsContent>
            <TabsContent value="matching"><MatchingPanel inv={inv} onRun={onRun} /></TabsContent>
            <TabsContent value="activity"><ActivityPanel inv={inv} /></TabsContent>
          </Tabs>
        </Card>
      </div>
      <ActionDialog inv={inv} kind={dialog} onClose={() => setDialog(null)} onRun={onRun} />
    </div>
  );
}
