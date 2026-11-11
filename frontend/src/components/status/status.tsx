"use client";
import { AlertTriangle, Ban, CheckCircle2, CircleDashed, CircleSlash, Clock, Loader2, ShieldAlert, XCircle } from "lucide-react";
import * as React from "react";

import { useReasonCodes } from "@/lib/api/hooks";
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

type Tone = "success" | "warning" | "danger" | "neutral" | "accent";
const TONE: Record<Tone, string> = {
  success: "bg-success-soft text-success border-success/20",
  warning: "bg-warning-soft text-warning border-warning/25",
  danger: "bg-danger-soft text-danger border-danger/20",
  neutral: "bg-neutral-soft text-neutral border-line",
  accent: "bg-accent-soft text-accent border-accent/20",
};

export function Badge({ tone = "neutral", children, className, icon }: { tone?: Tone; children: React.ReactNode;
  className?: string; icon?: React.ReactNode }) {
  return (
    <span className={cn("inline-flex h-[22px] items-center gap-1 whitespace-nowrap rounded-[5px] border px-1.5 text-[12px] font-medium [&_svg]:size-3.5",
      TONE[tone], className)}>
      {icon}{children}
    </span>
  );
}

const INVOICE_STATUS: Record<string, { tone: Tone; label: string; icon: React.ReactNode }> = {
  READY_FOR_APPROVAL: { tone: "success", label: "Ready for approval", icon: <CheckCircle2 /> },
  APPROVED: { tone: "accent", label: "Approved", icon: <CheckCircle2 /> },
  NEEDS_REVIEW: { tone: "warning", label: "Needs review", icon: <AlertTriangle /> },
  ON_HOLD: { tone: "warning", label: "On hold", icon: <Clock /> },
  REJECTED: { tone: "danger", label: "Rejected", icon: <Ban /> },
  FAILED: { tone: "neutral", label: "Technical failure", icon: <XCircle /> },
  CANCELLED: { tone: "neutral", label: "Cancelled", icon: <CircleSlash /> },
  PROCESSING: { tone: "accent", label: "Processing", icon: <Loader2 className="animate-spin" /> },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const s = INVOICE_STATUS[status] ?? { tone: "neutral" as Tone, label: humanize(status), icon: <CircleDashed /> };
  return <Badge tone={s.tone} icon={s.icon} className={className}>{s.label}</Badge>;
}

export function RunStatusBadge({ status }: { status: string }) {
  const map: Record<string, { tone: Tone; icon: React.ReactNode }> = {
    QUEUED: { tone: "neutral", icon: <Clock /> }, RUNNING: { tone: "accent", icon: <Loader2 className="animate-spin" /> },
    COMPLETED: { tone: "success", icon: <CheckCircle2 /> }, FAILED: { tone: "danger", icon: <XCircle /> },
  };
  const s = map[status] ?? { tone: "neutral" as Tone, icon: null };
  return <Badge tone={s.tone} icon={s.icon}>{humanize(status)}</Badge>;
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tone: Tone = severity === "BLOCKER" ? "danger" : severity === "REVIEW" ? "warning" :
    severity === "WARNING" ? "warning" : "neutral";
  return <Badge tone={tone} className="h-5 px-1 text-[10.5px] uppercase tracking-wide">{severity}</Badge>;
}

export function CheckIcon({ status, outcome, className }: { status: string; outcome?: string; className?: string }) {
  if (status === "PASS") return <CheckCircle2 className={cn("size-4 text-success", className)} aria-label="Passed" />;
  if (outcome === "NONE") return <AlertTriangle className={cn("size-4 text-ink-3", className)} aria-label="Information" />;
  if (status === "INDETERMINATE") return <CircleDashed className={cn("size-4 text-warning", className)} aria-label="Indeterminate" />;
  if (outcome === "REJECT") return <Ban className={cn("size-4 text-danger", className)} aria-label="Failed" />;
  return <XCircle className={cn("size-4", outcome === "HOLD" ? "text-warning" : "text-danger", className)} aria-label="Failed" />;
}

export function PriorityMark({ priority }: { priority: string }) {
  if (priority === "HIGH") return <Badge tone="danger" icon={<ShieldAlert />}>High</Badge>;
  if (priority === "LOW") return <span className="text-[12px] text-ink-3">Low</span>;
  return <span className="text-[12px] text-ink-2">Normal</span>;
}

export function Confidence({ value, threshold = 0.85, method }: { value: number; threshold?: number; method?: string | null }) {
  const pctv = Math.round(value * 100);
  const tone = method === "human" ? "bg-accent" : value >= threshold ? "bg-success" : value >= 0.6 ? "bg-warning" : "bg-danger";
  return (
    <span className="inline-flex items-center gap-1.5" title={`Confidence ${value.toFixed(2)}${method ? ` · ${method}` : ""}`}>
      <span className="relative h-1.5 w-10 overflow-hidden rounded-full bg-line">
        <span className={cn("absolute inset-y-0 left-0 rounded-full", tone)} style={{ width: `${pctv}%` }} />
      </span>
      <span className={cn("num text-[11.5px]", value < threshold && method !== "human" ? "text-warning font-medium" : "text-ink-3")}>
        {method === "human" ? "confirmed" : value.toFixed(2)}
      </span>
    </span>
  );
}

export function useReasonTitle() {
  const { data } = useReasonCodes();
  const map = React.useMemo(() => Object.fromEntries((data ?? []).map((r) => [r.code, r])), [data]);
  return (code: string) => map[code]?.title ?? humanize(code);
}

export function ReasonChip({ code }: { code: string }) {
  const title = useReasonTitle();
  const tone: Tone = ["VENDOR_BANK_DETAILS_CHANGED", "VENDOR_NOT_APPROVED", "INVOICE_DUPLICATE_SUSPECTED"].includes(code)
    ? "danger" : ["MANAGER_APPROVAL_REQUIRED", "INVOICE_NEAR_DUPLICATE"].includes(code) ? "neutral" : "warning";
  return <Badge tone={tone} className="font-normal" >{title(code)}</Badge>;
}

export function VendorStatus({ status }: { status: string }) {
  const tone: Tone = status === "APPROVED" ? "success" : status === "BLOCKED" ? "danger" : "warning";
  return <Badge tone={tone}>{humanize(status)}</Badge>;
}
