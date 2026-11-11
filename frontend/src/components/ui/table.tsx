import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export function Table({ className, ...p }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn("w-full border-collapse text-[13px]", className)} {...p} />
    </div>
  );
}
export function THead(p: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead {...p} className={cn("bg-surface-2/70", p.className)} />;
}
export function Th({ className, align, ...p }: React.ThHTMLAttributes<HTMLTableCellElement> & { align?: "right" | "left" }) {
  return <th className={cn("h-10 whitespace-nowrap border-b border-line px-4 text-left text-[12px] font-medium text-ink-3",
    align === "right" && "text-right", className)} {...p} />;
}
export function Td({ className, align, ...p }: React.TdHTMLAttributes<HTMLTableCellElement> & { align?: "right" | "left" }) {
  return <td className={cn("border-b border-line px-4 py-3 align-middle text-ink", align === "right" && "text-right num",
    className)} {...p} />;
}
export function Tr({ className, onClick, ...p }: React.HTMLAttributes<HTMLTableRowElement>) {
  return <tr onClick={onClick} className={cn(onClick && "cursor-pointer hover:bg-surface-2 [&>td:first-child]:hover:shadow-[inset_2px_0_0_var(--accent)]", "transition-colors", className)}
    {...p} />;
}

export function SortTh({ label, field, sort, order, onSort, align }: { label: string; field: string; sort: string;
  order: string; onSort: (field: string) => void; align?: "right" }) {
  const active = sort === field;
  const Icon = !active ? ArrowUpDown : order === "asc" ? ArrowUp : ArrowDown;
  return (
    <Th align={align} aria-sort={active ? (order === "asc" ? "ascending" : "descending") : "none"}>
      <button onClick={() => onSort(field)} className={cn("group inline-flex items-center gap-1 rounded hover:text-ink",
        align === "right" && "flex-row-reverse", active && "text-ink")}>
        {label}<Icon className={cn("size-3 transition-opacity", active ? "opacity-100 text-accent" : "opacity-40 group-hover:opacity-100")} />
      </button>
    </Th>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number;
  onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="flex items-center justify-between px-4 py-3 text-[12px] text-ink-3">
      <span className="num">{from}–{to} of {total}</span>
      <div className="flex items-center gap-1">
        <button aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}
          className="rounded p-1 hover:bg-surface-3 disabled:opacity-40"><ChevronLeft className="size-4" /></button>
        <span className="num px-1">Page {page} of {pages}</span>
        <button aria-label="Next page" disabled={page >= pages} onClick={() => onPage(page + 1)}
          className="rounded p-1 hover:bg-surface-3 disabled:opacity-40"><ChevronRight className="size-4" /></button>
      </div>
    </div>
  );
}

export function SkeletonRows({ rows = 6, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i}>{Array.from({ length: cols }).map((__, j) => (
          <td key={j} className="border-b border-line px-4 py-4"><div className="lf-pulse h-3.5 rounded bg-surface-3" /></td>
        ))}</tr>
      ))}
    </>
  );
}

export type SortState = { sort: string; order: "asc" | "desc" };

/** Client-side sorting for small, fully loaded tables. Accessors return a string, number or null. */
export function useClientSort<T>(rows: T[] | undefined,
  accessors: Record<string, (row: T) => string | number | null | undefined>, initial: SortState) {
  const [state, setState] = React.useState<SortState>(initial);
  const onSort = (field: string) => setState((s) => (s.sort === field
    ? { sort: field, order: s.order === "asc" ? "desc" : "asc" } : { sort: field, order: "asc" }));
  const sorted = React.useMemo(() => {
    if (!rows) return rows;
    const get = accessors[state.sort];
    if (!get) return rows;
    const dir = state.order === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const x = get(a), y = get(b);
      if (x === y) return 0;
      if (x === null || x === undefined || x === "") return 1;
      if (y === null || y === undefined || y === "") return -1;
      return (typeof x === "number" && typeof y === "number" ? x - y
        : String(x).localeCompare(String(y), undefined, { numeric: true })) * dir;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, state]);
  return { rows: sorted, sort: state.sort, order: state.order, onSort };
}
