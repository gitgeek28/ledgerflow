"use client";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Building2, ClipboardList, CornerDownLeft, FileText, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { StatusBadge } from "@/components/status/status";
import { api } from "@/lib/api/client";
import type { InvoiceListItem, Page, PurchaseOrder, Vendor } from "@/lib/api/types";
import { money } from "@/lib/format";
import { useDebounced } from "@/lib/hooks/use-debounced";
import { cn } from "@/lib/utils";

type Item = { key: string; group: string; label: string; sub?: string; href: string; icon: React.ReactNode;
  right?: React.ReactNode };

const PAGES: Item[] = [
  ["Overview", "/"], ["Invoices", "/invoices"], ["Upload invoices", "/invoices/new"], ["Review queue", "/review"],
  ["Processing runs", "/runs"], ["Purchase orders", "/purchase-orders"], ["Vendors", "/vendors"],
  ["Audit log", "/audit"], ["Policies", "/policies"],
].map(([label, href]) => ({ key: `page:${href}`, group: "Go to", label, href, icon: <CornerDownLeft /> }));

export function useCommandPalette() {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return { open, setOpen };
}

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const [q, setQ] = React.useState("");
  const dq = useDebounced(q, 180);
  const [items, setItems] = React.useState<Item[]>(PAGES);
  const [active, setActive] = React.useState(0);

  React.useEffect(() => { if (!open) { setQ(""); setActive(0); } }, [open]);
  React.useEffect(() => {
    let cancelled = false;
    const pages = PAGES.filter((p) => p.label.toLowerCase().includes(dq.toLowerCase()));
    if (!dq.trim()) { setItems(PAGES); return; }
    Promise.all([
      api.get<Page<InvoiceListItem>>("/invoices", { q: dq, page_size: 6 }).catch(() => null),
      api.get<Page<Vendor>>("/vendors", { q: dq, page_size: 4 }).catch(() => null),
      api.get<Page<PurchaseOrder>>("/purchase-orders", { q: dq, page_size: 4 }).catch(() => null),
    ]).then(([inv, ven, pos]) => {
      if (cancelled) return;
      setItems([
        ...(inv?.items ?? []).map((i) => ({ key: i.id, group: "Invoices", href: `/invoices/${i.id}`, icon: <FileText />,
          label: `${i.invoice_number ?? i.reference}`, sub: `${i.reference} · ${i.vendor?.legal_name ?? i.vendor_name_raw ?? "Unresolved vendor"} · ${money(i.grand_total, i.currency)}`,
          right: <StatusBadge status={i.status} /> })),
        ...(ven?.items ?? []).map((v) => ({ key: v.id, group: "Vendors", href: `/vendors/${v.id}`, icon: <Building2 />,
          label: v.legal_name, sub: `${v.vendor_code} · ${v.city}` })),
        ...(pos?.items ?? []).map((p) => ({ key: p.id, group: "Purchase orders", href: `/purchase-orders/${p.id}`,
          icon: <ClipboardList />, label: p.po_number, sub: `${p.vendor.legal_name} · ${p.description}` })),
        ...pages,
      ]);
      setActive(0);
    });
    return () => { cancelled = true; };
  }, [dq]);

  function go(item?: Item) {
    if (!item) return;
    onOpenChange(false);
    router.push(item.href);
  }

  let lastGroup = "";
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/25 backdrop-blur-[2px]" />
        <DialogPrimitive.Content aria-describedby={undefined}
          className="lf-enter fixed left-1/2 top-[14vh] z-50 w-[calc(100vw-32px)] max-w-xl -translate-x-1/2 overflow-hidden rounded-2xl border border-line bg-surface shadow-pop">
          <DialogPrimitive.Title className="sr-only">Search LedgerFlow</DialogPrimitive.Title>
          <div className="flex items-center gap-2.5 border-b border-line px-4">
            <Search className="size-4 text-ink-3" />
            <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search everything"
              placeholder="Search invoices, vendors, POs, or jump to a page…"
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(items.length - 1, a + 1)); }
                if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
                if (e.key === "Enter") go(items[active]);
              }}
              className="h-12 flex-1 bg-transparent text-[14px] text-ink outline-none placeholder:text-ink-3" />
            <kbd className="rounded border border-line px-1.5 text-[11px] text-ink-3">esc</kbd>
          </div>
          <ul className="max-h-[50vh] overflow-y-auto p-2" role="listbox">
            {items.length === 0 && <li className="px-3 py-6 text-center text-[13px] text-ink-3">No matches for “{q}”</li>}
            {items.map((it, i) => {
              const header = it.group !== lastGroup ? it.group : null;
              lastGroup = it.group;
              return (
                <React.Fragment key={it.key}>
                  {header && <li className="px-3 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wide text-ink-3">{header}</li>}
                  <li role="option" aria-selected={i === active} onMouseEnter={() => setActive(i)} onClick={() => go(it)}
                    className={cn("flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2", i === active && "bg-surface-3")}>
                    <span className="flex size-8 items-center justify-center rounded-lg bg-surface-3 text-ink-2 [&_svg]:size-4">{it.icon}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] font-medium text-ink">{it.label}</span>
                      {it.sub && <span className="block truncate text-[12px] text-ink-3">{it.sub}</span>}
                    </span>
                    {it.right}
                  </li>
                </React.Fragment>
              );
            })}
          </ul>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
