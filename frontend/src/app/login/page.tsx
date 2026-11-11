"use client";
import { ArrowRight, CheckCircle2, FileSearch, ShieldCheck, Workflow } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { LogoMark, Wordmark } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { Avatar, Input, Label } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api/client";
import { useDemoUsers } from "@/lib/api/hooks";
import type { User } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const ROLE_NOTE: Record<string, string> = {
  AP_ANALYST: "Uploads, reviews and resolves exceptions",
  AP_MANAGER: "Approves, overrides blockers, edits policy",
  AUDITOR: "Read-only access to runs and audit trail",
};

const POINTS = [
  { icon: <FileSearch />, title: "Reads every invoice", text: "Text PDFs and scans, with evidence for each field." },
  { icon: <Workflow />, title: "Reconciles against POs and receipts", text: "Price, quantity, tax and cumulative PO balance." },
  { icon: <ShieldCheck />, title: "Explains every decision", text: "Deterministic rules, reason codes and a complete audit trail." },
];

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { data: users } = useDemoUsers();
  const [email, setEmail] = React.useState("aisha.rao@kestrel.example");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post<{ user: User }>("/auth/login", { email, password });
      router.replace(params.get("next") || "/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen bg-bg lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-[#0f1020] p-12 text-white lg:flex lg:flex-col">
        <div className="relative flex items-center gap-2.5"><LogoMark className="size-8" /><span className="text-[16px] font-semibold">LedgerFlow</span></div>
        <div className="relative mt-auto max-w-md">
          <h2 className="text-[34px] font-semibold leading-tight tracking-tight">From invoice PDF to a decision you can defend.</h2>
          <p className="mt-3 text-[14px] text-white/70">Accounts payable automation that keeps people in control of exceptions.</p>
          <ul className="mt-8 space-y-4">
            {POINTS.map((p) => (
              <li key={p.title} className="flex gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-white/10 [&_svg]:size-[18px]">{p.icon}</span>
                <span><span className="block text-[14px] font-medium">{p.title}</span><span className="block text-[13px] text-white/60">{p.text}</span></span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative mt-10 text-[12px] text-white/40">Case-study build · synthetic data only</p>
      </aside>
      <div className="flex flex-col">
        <div className="flex items-center justify-between px-6 py-5">
          <span className="lg:invisible"><Wordmark /></span>
          <ThemeToggle />
        </div>
        <div className="flex flex-1 items-center justify-center px-4 pb-16">
          <div className="w-full max-w-[420px]">
            <h1 className="text-[26px] font-semibold tracking-tight">Welcome back</h1>
            <p className="mt-1 text-[13.5px] text-ink-3">Sign in to the Kestrel Components AP workspace (fictional company, synthetic documents).</p>
            <form onSubmit={submit} className="mt-7 space-y-5">
              <div>
                <Label>Choose a demo user</Label>
                <div className="space-y-2" role="radiogroup">
                  {(users ?? []).map((u) => (
                    <button type="button" key={u.id} role="radio" aria-checked={email === u.email} onClick={() => setEmail(u.email)}
                      className={cn("flex w-full items-center gap-3 rounded-2xl border bg-surface px-3.5 py-3 text-left transition-all",
                        email === u.email ? "border-accent shadow-[0_0_0_3px_var(--highlight)]" : "border-line hover:border-line-strong")}>
                      <Avatar name={u.name} className="size-9" />
                      <span className="min-w-0 flex-1">
                        <span className="block text-[13.5px] font-medium text-ink">{u.name} <span className="font-normal text-ink-3">· {u.title}</span></span>
                        <span className="block text-[12px] text-ink-3">{ROLE_NOTE[u.role]}</span>
                      </span>
                      {email === u.email && <CheckCircle2 className="size-[18px] text-accent" />}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <Label htmlFor="pw">Demo password</Label>
                <Input id="pw" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder="ledgerflow-demo" autoComplete="current-password" className="h-10" />
                <p className="mt-1.5 text-[12px] text-ink-3">Shared demo password: <span className="font-mono">ledgerflow-demo</span></p>
              </div>
              {error && <p className="rounded-xl bg-danger-soft px-3 py-2 text-[12.5px] text-danger" role="alert">{error}</p>}
              <Button variant="primary" className="w-full" size="lg" loading={busy} type="submit">Sign in <ArrowRight /></Button>
            </form>
            <p className="mt-6 text-center text-[12px] text-ink-3">Demo authentication, not production identity.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return <React.Suspense><LoginForm /></React.Suspense>;
}
