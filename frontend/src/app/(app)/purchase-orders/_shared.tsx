"use client";
import * as React from "react";

import { Badge } from "@/components/status/status";
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

export function useDebounced<T>(value: T, delay = 250): T {
  const [v, setV] = React.useState(value);
  React.useEffect(() => {
    const t = setTimeout(() => setV(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return v;
}

export function POStatusBadge({ status }: { status: string }) {
  return <Badge tone={status === "OPEN" ? "success" : "neutral"}>{humanize(status)}</Badge>;
}

/** Display-only ratio bar; amounts stay decimal strings everywhere else. */
export function ConsumptionBar({ used, total, className }: { used: string | number | null; total: string | number | null;
  className?: string }) {
  const t = Number(total ?? 0);
  const ratio = t > 0 ? Math.min(1, Math.max(0, Number(used ?? 0) / t)) : 0;
  return (
    <span className={cn("relative block h-1.5 w-16 overflow-hidden rounded-full bg-line", className)}
      role="img" aria-label={`${Math.round(ratio * 100)}% consumed`}>
      <span className={cn("absolute inset-y-0 left-0 rounded-full", ratio >= 1 ? "bg-warning" : "bg-accent")}
        style={{ width: `${ratio * 100}%` }} />
    </span>
  );
}
