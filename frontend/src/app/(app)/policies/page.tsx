"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Lock, SlidersHorizontal } from "lucide-react";
import * as React from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { PageHeader } from "@/components/layout/shell";
import { Badge, SeverityBadge } from "@/components/status/status";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, EmptyState, ErrorState, Input, Kv, Label, Select, Skeleton, Textarea }
  from "@/components/ui/primitives";
import { SkeletonRows, Table, Td, Th, THead, Tr } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api/client";
import { useMe, usePolicies, useReasonCodes } from "@/lib/api/hooks";
import type { Policy } from "@/lib/api/types";
import { date, dateTime, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

// Mirrors backend PolicySettings constraints (backend/app/services/policy.py). The server re-validates.
function dec(min: number, max: number, places = 2) {
  const rx = new RegExp(`^\\d+(\\.\\d{1,${places}})?$`);
  return z.string().trim()
    .regex(rx, `Enter a number with at most ${places} decimal places`)
    .refine((v) => Number(v) >= min && Number(v) <= max, `Must be between ${min} and ${max.toLocaleString("en-IN")}`);
}

const schema = z.object({
  unit_price_variance_pct: dec(0, 50),
  invoice_total_variance_abs: dec(0, 1_000_000),
  quantity_variance_pct: dec(0, 50),
  rounding_tolerance_abs: dec(0, 100),
  critical_field_confidence: dec(0, 1),
  po_candidate_min_score: dec(0, 1),
  po_candidate_min_margin: dec(0, 1),
  vendor_fuzzy_min_score: dec(0, 1),
  vendor_fuzzy_min_margin: dec(0, 1),
  line_match_min_similarity: dec(0, 1),
  require_grn_for_goods: z.boolean(),
  near_duplicate_window_days: z.string().trim().regex(/^\d+$/, "Whole days only")
    .refine((v) => Number(v) <= 365, "Must be between 0 and 365"),
  near_duplicate_amount_pct: dec(0, 20),
  manager_approval_above: dec(0, 1_000_000_000),
  blocked_vendor_outcome: z.enum(["REJECT", "HOLD"]),
  change_note: z.string().trim().min(3, "Describe why the policy is changing (min 3 characters)").max(500),
});
type FormValues = z.infer<typeof schema>;
type FieldKey = Exclude<keyof FormValues, "change_note">;

const FIELDS: { group: string; items: { key: FieldKey; label: string; unit: string; impact: string }[] }[] = [
  { group: "Financial tolerances", items: [
    { key: "unit_price_variance_pct", label: "Unit price variance", unit: "%",
      impact: "Invoice lines priced more than this % above the PO price go to review." },
    { key: "invoice_total_variance_abs", label: "Invoice amount variance", unit: "INR",
      impact: "Subtotals more than this above the PO-priced value of the invoiced quantities go to review." },
    { key: "quantity_variance_pct", label: "Quantity variance", unit: "%",
      impact: "Allowed over-billing versus remaining ordered / received quantity. 0 means no over-billing." },
    { key: "rounding_tolerance_abs", label: "Rounding tolerance", unit: "INR",
      impact: "Largest arithmetic difference (lines, subtotal, tax, total) treated as rounding." },
  ] },
  { group: "Extraction and matching", items: [
    { key: "critical_field_confidence", label: "Critical field confidence", unit: "0–1",
      impact: "Invoice number, date or total read below this confidence must be confirmed by a person." },
    { key: "po_candidate_min_score", label: "PO auto-select score", unit: "0–1",
      impact: "Without a PO reference, the best-ranked PO is only auto-selected at or above this score." },
    { key: "po_candidate_min_margin", label: "PO auto-select margin", unit: "0–1",
      impact: "…and only if it beats the runner-up by at least this margin; otherwise a reviewer chooses." },
    { key: "vendor_fuzzy_min_score", label: "Vendor name match score", unit: "0–1",
      impact: "Fuzzy name matches below this similarity are not accepted as the vendor." },
    { key: "vendor_fuzzy_min_margin", label: "Vendor name match margin", unit: "0–1",
      impact: "Closer competing vendor names than this are treated as ambiguous." },
    { key: "line_match_min_similarity", label: "Line description similarity", unit: "0–1",
      impact: "Invoice lines less similar than this to every PO line are reported as unmatched." },
  ] },
  { group: "Controls", items: [
    { key: "require_grn_for_goods", label: "Require goods receipt for goods POs", unit: "",
      impact: "When on, goods invoices with no posted GRN are held until goods are received." },
    { key: "near_duplicate_window_days", label: "Near-duplicate window", unit: "days",
      impact: "Similar invoices from the same vendor within this window are flagged for awareness." },
    { key: "near_duplicate_amount_pct", label: "Near-duplicate amount band", unit: "%",
      impact: "Totals within this % of a prior invoice count towards the near-duplicate rule." },
    { key: "manager_approval_above", label: "Manager approval threshold", unit: "INR",
      impact: "Invoices above this value can only be approved by an AP manager." },
    { key: "blocked_vendor_outcome", label: "Blocked vendor outcome", unit: "",
      impact: "What happens to invoices from blocked vendors: reject outright, or hold." },
  ] },
];

const RESOLUTION: Record<string, string> = {
  ACCEPT: "Reviewer may accept with a reason", CORRECT: "Fix the data / selection, then re-run",
  OVERRIDE: "Manager-only, audited override", NONE: "Cannot be cleared by a reviewer",
};

function toForm(p: Policy): FormValues {
  const s = p.settings;
  const str = (k: string) => String(s[k] ?? "");
  return {
    unit_price_variance_pct: str("unit_price_variance_pct"), invoice_total_variance_abs: str("invoice_total_variance_abs"),
    quantity_variance_pct: str("quantity_variance_pct"), rounding_tolerance_abs: str("rounding_tolerance_abs"),
    critical_field_confidence: str("critical_field_confidence"), po_candidate_min_score: str("po_candidate_min_score"),
    po_candidate_min_margin: str("po_candidate_min_margin"), vendor_fuzzy_min_score: str("vendor_fuzzy_min_score"),
    vendor_fuzzy_min_margin: str("vendor_fuzzy_min_margin"), line_match_min_similarity: str("line_match_min_similarity"),
    require_grn_for_goods: Boolean(s.require_grn_for_goods), near_duplicate_window_days: str("near_duplicate_window_days"),
    near_duplicate_amount_pct: str("near_duplicate_amount_pct"), manager_approval_above: str("manager_approval_above"),
    blocked_vendor_outcome: s.blocked_vendor_outcome === "HOLD" ? "HOLD" : "REJECT", change_note: "",
  };
}

function PolicyForm({ current, canEdit }: { current: Policy; canEdit: boolean }) {
  const qc = useQueryClient();
  const { register, handleSubmit, reset, setError, formState: { errors, isSubmitting, isDirty } } =
    useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: toForm(current) });
  React.useEffect(() => reset(toForm(current)), [current, reset]);
  const [serverError, setServerError] = React.useState<string | null>(null);

  async function onSubmit(values: FormValues) {
    setServerError(null);
    const { change_note, ...rest } = values;
    const settings = { ...rest, near_duplicate_window_days: Number(rest.near_duplicate_window_days) };
    try {
      const saved = await api.post<Policy>("/policies", { settings, change_note });
      toast.success(`Policy v${saved.version} saved — new runs use it; past runs keep the version they used`);
      await qc.invalidateQueries({ queryKey: ["policies"] });
    } catch (err) {
      if (err instanceof ApiError) {
        const details = Array.isArray(err.details) ? (err.details as { loc: (string | number)[]; msg: string }[]) : [];
        for (const d of details) {
          const key = String(d.loc[d.loc.length - 1]) as keyof FormValues;
          if (key in values) setError(key, { message: d.msg });
        }
        setServerError(err.message);
      } else {
        setServerError("Could not save the policy.");
      }
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <fieldset disabled={!canEdit} className="divide-y divide-line">
        {FIELDS.map((g) => (
          <div key={g.group} className="px-4 py-4">
            <h4 className="mb-3 text-[11.5px] font-semibold uppercase tracking-wide text-ink-3">{g.group}</h4>
            <div className="grid gap-x-6 gap-y-4 md:grid-cols-2">
              {g.items.map((f) => {
                const err = errors[f.key]?.message;
                return (
                  <div key={f.key}>
                    {f.key === "require_grn_for_goods" ? (
                      <label className="flex items-center gap-2 text-[13px] font-medium text-ink">
                        <input type="checkbox" {...register(f.key)} className="size-4 accent-[var(--accent)]" />
                        {f.label}
                      </label>
                    ) : (
                      <>
                        <Label htmlFor={f.key}>{f.label}{f.unit && <span className="ml-1 font-normal text-ink-3">({f.unit})</span>}</Label>
                        {f.key === "blocked_vendor_outcome" ? (
                          <Select id={f.key} {...register(f.key)} className="w-full">
                            <option value="REJECT">Reject</option>
                            <option value="HOLD">Hold</option>
                          </Select>
                        ) : (
                          <Input id={f.key} inputMode="decimal" {...register(f.key)} aria-invalid={!!err}
                            className={cn("num", err && "border-danger")} />
                        )}
                      </>
                    )}
                    <p className="mt-1 text-[12px] text-ink-3">{f.impact}</p>
                    {err && <p className="mt-0.5 text-[12px] text-danger" role="alert">{err}</p>}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
        <div className="px-4 py-4">
          <Label htmlFor="change_note">Change note</Label>
          <Textarea id="change_note" rows={2} {...register("change_note")}
            placeholder="Why is the policy changing? e.g. 'Tighten price tolerance after Q3 audit finding'" />
          {errors.change_note && <p className="mt-0.5 text-[12px] text-danger" role="alert">{errors.change_note.message}</p>}
        </div>
      </fieldset>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface-2 px-4 py-3">
        {canEdit ? (
          <p className="text-[12px] text-ink-3">Saving creates a new version. Historical runs keep the policy version they used.</p>
        ) : (
          <p className="flex items-center gap-1.5 text-[12px] text-ink-3"><Lock className="size-3.5" />
            Read-only: only an AP manager can create a new policy version.</p>
        )}
        <div className="flex items-center gap-2">
          {serverError && <span className="text-[12px] text-danger" role="alert">{serverError}</span>}
          {canEdit && (
            <>
              <Button type="button" variant="ghost" disabled={!isDirty || isSubmitting} onClick={() => reset(toForm(current))}>Reset</Button>
              <Button type="submit" variant="primary" loading={isSubmitting}>Save as v{current.version + 1}</Button>
            </>
          )}
        </div>
      </div>
    </form>
  );
}

export default function PoliciesPage() {
  const { data: me } = useMe();
  const { data: policies, isLoading, isError, error, refetch } = usePolicies();
  const { data: codes, isLoading: codesLoading } = useReasonCodes();
  const current = policies?.find((p) => p.is_active) ?? policies?.[0];
  const canEdit = me?.role === "AP_MANAGER";

  return (
    <div className="space-y-5">
      <PageHeader title="Policies"
        description="Tolerances and controls applied by the deterministic decision engine. Defaults are an illustrative demo policy, not accounting advice." />
      {isError && <ErrorState error={error} onRetry={() => refetch()} />}

      <div className="grid gap-5 xl:grid-cols-[320px_1fr]">
        <Card className="h-fit">
          <CardHeader title="Current version" description="Every run records the exact version it used." />
          {isLoading || !current ? (
            <div className="space-y-2 p-4"><Skeleton className="h-4 w-24" /><Skeleton className="h-4 w-40" /><Skeleton className="h-4 w-32" /></div>
          ) : (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 p-4">
              <Kv label="Version"><span className="flex items-center gap-2 font-semibold">v{current.version}<Badge tone="success">Active</Badge></span></Kv>
              <Kv label="Effective">{date(current.effective_from)}</Kv>
              <Kv label="Created by">{current.created_by ?? "System seed"}</Kv>
              <Kv label="Runs using it"><span className="num">{current.runs_using}</span></Kv>
              <div className="col-span-2">
                <dt className="text-[11.5px] font-medium uppercase tracking-wide text-ink-3">Change note</dt>
                <dd className="mt-0.5 text-[13px] text-ink-2">{current.change_note ?? "—"}</dd>
              </div>
            </dl>
          )}
        </Card>
        <Card>
          <CardHeader title="Settings" description={canEdit ? "Edit and save to create a new version." : "Viewing the active settings."} />
          {current ? <PolicyForm current={current} canEdit={canEdit} /> : <div className="space-y-3 p-4">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-9" />)}</div>}
        </Card>
      </div>

      <Card>
        <CardHeader title="Version history" description="Policies are never edited in place." />
        <Table>
          <THead><tr><Th>Version</Th><Th>Effective</Th><Th>Created by</Th><Th align="right">Runs using</Th><Th>Note</Th><Th>Status</Th></tr></THead>
          <tbody>
            {isLoading ? <SkeletonRows rows={2} cols={6} /> : (policies ?? []).map((p) => (
              <Tr key={p.id}>
                <Td className="font-medium">v{p.version}</Td>
                <Td className="whitespace-nowrap text-ink-2">{dateTime(p.effective_from)}</Td>
                <Td className="text-ink-2">{p.created_by ?? "System seed"}</Td>
                <Td align="right">{p.runs_using}</Td>
                <Td className="max-w-[420px]"><span className="block truncate text-ink-2" title={p.change_note ?? undefined}>{p.change_note ?? "—"}</span></Td>
                <Td>{p.is_active ? <Badge tone="success">Active</Badge> : <Badge>Superseded</Badge>}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        {!isLoading && policies?.length === 0 && <EmptyState icon={<SlidersHorizontal />} title="No policy configured"
          description="Run the seed command to create the demo policy." />}
      </Card>

      <Card>
        <CardHeader title="Reason codes" description="Stable, machine-readable codes attached to every check and decision." />
        <Table>
          <THead><tr><Th>Code</Th><Th>Title</Th><Th>Severity</Th><Th>Outcome on failure</Th><Th>Resolution</Th><Th>Description</Th></tr></THead>
          <tbody>
            {codesLoading ? <SkeletonRows rows={8} cols={6} /> : (codes ?? []).map((c) => (
              <Tr key={c.code}>
                <Td className="whitespace-nowrap font-mono text-[12px]">{c.code}</Td>
                <Td className="whitespace-nowrap font-medium">{c.title}</Td>
                <Td><SeverityBadge severity={c.severity} /></Td>
                <Td className="whitespace-nowrap text-ink-2">{c.outcome === "NONE" ? "Informational" : humanize(c.outcome)}</Td>
                <Td className="whitespace-nowrap text-ink-2" title={c.resolution}>{RESOLUTION[c.resolution] ?? c.resolution}</Td>
                <Td className="min-w-[280px] text-[12.5px] text-ink-2">{c.description}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}
