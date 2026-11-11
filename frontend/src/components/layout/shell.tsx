"use client";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import {
  Building2, ClipboardList, FileStack, Gauge, History, Inbox, LogOut, Menu, PlayCircle, ScrollText, SlidersHorizontal,
  Upload, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";

import { Wordmark } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { Tip } from "@/components/ui/overlays";
import { Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api/client";
import { useMe, useReadiness, useReviewQueue } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

const NAV = [
  { group: "Operate", items: [
    { href: "/", label: "Overview", icon: Gauge },
    { href: "/invoices", label: "Invoices", icon: FileStack },
    { href: "/review", label: "Review queue", icon: Inbox, badge: "queue" },
    { href: "/runs", label: "Processing runs", icon: PlayCircle },
  ] },
  { group: "Reference", items: [
    { href: "/purchase-orders", label: "Purchase orders", icon: ClipboardList },
    { href: "/vendors", label: "Vendors", icon: Building2 },
  ] },
  { group: "Governance", items: [
    { href: "/audit", label: "Audit log", icon: History },
    { href: "/policies", label: "Policies", icon: SlidersHorizontal },
  ] },
];

function isActive(path: string, href: string) {
  return href === "/" ? path === "/" : path === href || path.startsWith(href + "/");
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  const { data: queue } = useReviewQueue("open");
  return (
    <nav className="flex h-full flex-col" aria-label="Main">
      <div className="px-4 py-4"><Wordmark /></div>
      <div className="flex-1 space-y-5 overflow-y-auto px-2.5 pb-4">
        {NAV.map((g) => (
          <div key={g.group}>
            <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-ink-3">{g.group}</div>
            <ul className="space-y-0.5">
              {g.items.map((it) => {
                const active = isActive(path, it.href);
                const Icon = it.icon;
                return (
                  <li key={it.href}>
                    <Link href={it.href} onClick={onNavigate} aria-current={active ? "page" : undefined}
                      className={cn("flex h-8 items-center gap-2.5 rounded-md px-2 text-[13px] text-ink-2 hover:bg-surface-3 hover:text-ink",
                        active && "bg-surface text-ink font-medium shadow-card border border-line")}>
                      <Icon className={cn("size-4", active ? "text-accent" : "text-ink-3")} />
                      <span className="flex-1">{it.label}</span>
                      {it.badge === "queue" && queue && queue.length > 0 && (
                        <span className="num rounded bg-warning-soft px-1.5 text-[11px] font-medium text-warning">{queue.length}</span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
      <SystemStatus />
    </nav>
  );
}

function SystemStatus() {
  const { data } = useReadiness();
  if (!data) return <div className="px-4 pb-4"><Skeleton className="h-14" /></div>;
  const rows = [
    { label: "Database", ok: data.database, detail: data.database ? `policy v${data.policy_version}` : "unreachable" },
    { label: "OCR", ok: !!data.ocr?.available, detail: data.ocr?.available ? "Tesseract" : "not installed" },
    { label: "Local LLM", ok: !!data.llm?.model_available, optional: true,
      detail: data.llm?.provider === "none" ? "disabled" : data.llm?.model_available ? data.llm.model : "offline (rules only)" },
    { label: "Queue", ok: true, detail: `${data.queue?.queued ?? 0} queued · ${data.queue?.running ?? 0} running` },
  ];
  return (
    <div className="mx-2.5 mb-3 rounded-md border border-line bg-surface-2 px-3 py-2.5">
      <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-3">System</div>
      <ul className="space-y-1">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between text-[12px]">
            <span className="flex items-center gap-1.5 text-ink-2">
              <span className={cn("size-1.5 rounded-full", r.ok ? "bg-success" : r.optional ? "bg-ink-3" : "bg-danger")} />
              {r.label}
            </span>
            <span className="truncate pl-2 text-ink-3">{r.detail}</span>
          </li>
        ))}
      </ul>
      {data.demo_stage_pacing_ms > 0 && (
        <p className="mt-1.5 text-[11px] text-warning">Demo pacing on: {data.demo_stage_pacing_ms} ms pause between stages (not counted in durations)</p>
      )}
    </div>
  );
}

function UserMenu() {
  const { data: me } = useMe();
  const router = useRouter();
  if (!me) return <Skeleton className="h-8 w-28" />;
  const initials = me.name.split(" ").map((p) => p[0]).join("").slice(0, 2);
  return (
    <Dropdown.Root>
      <Dropdown.Trigger className="flex items-center gap-2 rounded-md py-1 pl-1 pr-2 hover:bg-surface-3" aria-label="Account menu">
        <span className="flex size-7 items-center justify-center rounded-full bg-accent-soft text-[11px] font-semibold text-accent">{initials}</span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-[12.5px] font-medium text-ink">{me.name}</span>
          <span className="block text-[11px] text-ink-3">{me.title}</span>
        </span>
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content align="end" sideOffset={6} className="z-50 min-w-48 rounded-md border border-line bg-surface p-1 shadow-lg">
          <div className="px-2 py-1.5 text-[12px] text-ink-3">{me.email}</div>
          <Dropdown.Separator className="my-1 h-px bg-line" />
          <Dropdown.Item onSelect={async () => { await api.post("/auth/logout"); router.replace("/login"); }}
            className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-[13px] text-ink outline-none data-[highlighted]:bg-surface-3">
            <LogOut className="size-4" /> Sign out
          </Dropdown.Item>
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: me, isLoading, isError } = useMe();
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => { if (isError) router.replace("/login"); }, [isError, router]);
  if (isLoading || !me) {
    return <div className="flex min-h-screen items-center justify-center text-[13px] text-ink-3">Loading workspace…</div>;
  }
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 border-r border-line bg-surface-2 lg:block">
        <Sidebar />
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-[260px] border-r border-line bg-surface-2">
            <button className="absolute right-2 top-3 rounded p-1 text-ink-3" onClick={() => setOpen(false)} aria-label="Close menu"><X className="size-4" /></button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-12 items-center gap-2 border-b border-line bg-bg/90 px-4 backdrop-blur">
          <button className="rounded p-1.5 text-ink-2 hover:bg-surface-3 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu className="size-4" />
          </button>
          <div className="flex-1" />
          {me.role !== "AUDITOR" && (
            <Button variant="primary" size="sm" asChild>
              <Link href="/invoices/new"><Upload className="size-3.5" />Upload invoices</Link>
            </Button>
          )}
          <Tip content="API documentation (OpenAPI)" side="bottom">
            <a href="/api/docs" target="_blank" rel="noreferrer"
              className="hidden h-8 w-8 items-center justify-center rounded-md text-ink-2 hover:bg-surface-3 sm:inline-flex" aria-label="API docs">
              <ScrollText className="size-4" />
            </a>
          </Tip>
          <ThemeToggle />
          <div className="mx-1 h-5 w-px bg-line" />
          <UserMenu />
        </header>
        <main className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}

export function PageHeader({ title, description, actions, crumbs }: { title: React.ReactNode;
  description?: React.ReactNode; actions?: React.ReactNode; crumbs?: { href?: string; label: string }[] }) {
  return (
    <div className="mb-5">
      {crumbs && (
        <nav aria-label="Breadcrumb" className="mb-1.5 flex flex-wrap items-center gap-1 text-[12px] text-ink-3">
          {crumbs.map((c, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span aria-hidden>/</span>}
              {c.href ? <Link href={c.href} className="hover:text-ink">{c.label}</Link> : <span className="text-ink-2">{c.label}</span>}
            </React.Fragment>
          ))}
        </nav>
      )}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-[20px] font-semibold tracking-tight text-ink">{title}</h1>
          {description && <p className="mt-0.5 text-[13px] text-ink-3">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
