import { format, formatDistanceToNowStrict, parseISO } from "date-fns";

// Display-only formatting. Values arrive as decimal strings; Intl formats the string's numeric value for display.
// No client-side arithmetic is performed on money.
const inr = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const inrCompact = new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 });

export function money(value: string | null | undefined, currency: string | null = "INR", compact = false): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  const body = compact ? inrCompact.format(n) : inr.format(n);
  return currency ? `${currency === "INR" ? "₹" : currency + " "}${body}` : body;
}

export function qty(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  return Number.isNaN(n) ? value : new Intl.NumberFormat("en-IN", { maximumFractionDigits: 3 }).format(n);
}

export function date(value: string | null | undefined): string {
  if (!value) return "—";
  return format(parseISO(value), "dd MMM yyyy");
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return format(parseISO(value), "dd MMM yyyy, HH:mm:ss");
}

export function time(value: string | null | undefined): string {
  if (!value) return "—";
  return format(parseISO(value), "HH:mm:ss.SSS");
}

export function ago(value: string | null | undefined): string {
  if (!value) return "—";
  return `${formatDistanceToNowStrict(parseISO(value))} ago`;
}

export function age(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return "—";
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))}m`;
  if (hours < 48) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

export function ms(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(value < 10_000 ? 2 : 1)} s`;
}

export function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function humanize(s: string | null | undefined): string {
  if (!s) return "—";
  const t = s.replace(/_/g, " ").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export const STAGES: { key: string; label: string; description: string }[] = [
  { key: "RECEIVED", label: "Received", description: "File stored under a server-generated key" },
  { key: "FILE_VALIDATION", label: "File validation", description: "PDF structure, pages, encryption" },
  { key: "TEXT_EXTRACTION", label: "Text extraction", description: "Embedded text layer, OCR for scanned pages" },
  { key: "FIELD_EXTRACTION", label: "Field extraction", description: "Header fields and line items with evidence" },
  { key: "VENDOR_RESOLUTION", label: "Vendor resolution", description: "GSTIN, name and alias matching" },
  { key: "PO_MATCHING", label: "PO matching", description: "PO reference or ranked candidates, line matching" },
  { key: "FINANCIAL_RECONCILIATION", label: "Financial reconciliation",
    description: "Arithmetic, price, quantity, receipts, PO balance" },
  { key: "DUPLICATE_CHECK", label: "Duplicate check", description: "Business key and near-duplicate rules" },
  { key: "RISK_AND_POLICY_CHECKS", label: "Risk & policy", description: "Vendor status, bank details, confidence" },
  { key: "DECISION", label: "Decision", description: "Deterministic decision matrix" },
];
export const STAGE_LABEL: Record<string, string> = Object.fromEntries(STAGES.map((s) => [s.key, s.label]));
