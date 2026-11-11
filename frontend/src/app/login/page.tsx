"use client";
import { ArrowRight } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { Wordmark } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { Card, Input, Label } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api/client";
import { useDemoUsers } from "@/lib/api/hooks";
import type { User } from "@/lib/api/types";
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

const ROLE_NOTE: Record<string, string> = {
  AP_ANALYST: "Uploads, reviews and resolves exceptions",
  AP_MANAGER: "Approves, overrides blockers, edits policy",
  AUDITOR: "Read-only access to runs and audit trail",
};

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
    <div className="flex min-h-screen flex-col bg-bg">
      <div className="flex items-center justify-between px-6 py-4">
        <Wordmark />
        <ThemeToggle />
      </div>
      <div className="flex flex-1 items-center justify-center px-4 pb-16">
        <Card className="w-full max-w-[440px] p-6">
          <h1 className="text-[18px] font-semibold tracking-tight">Sign in</h1>
          <p className="mt-1 text-[13px] text-ink-3">
            Demo environment for a fictional buyer, Kestrel Components. All documents and records are synthetic.
          </p>
          <form onSubmit={submit} className="mt-5 space-y-4">
            <div>
              <Label>Choose a demo user</Label>
              <div className="space-y-1.5" role="radiogroup">
                {(users ?? []).map((u) => (
                  <button type="button" key={u.id} role="radio" aria-checked={email === u.email}
                    onClick={() => setEmail(u.email)}
                    className={cn("flex w-full items-center justify-between rounded-md border px-3 py-2 text-left transition-colors",
                      email === u.email ? "border-accent bg-accent-soft" : "border-line hover:bg-surface-2")}>
                    <span>
                      <span className="block text-[13px] font-medium text-ink">{u.name}</span>
                      <span className="block text-[12px] text-ink-3">{ROLE_NOTE[u.role]}</span>
                    </span>
                    <span className="text-[11.5px] text-ink-2">{humanize(u.role).replace("Ap ", "AP ")}</span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <Label htmlFor="pw">Demo password</Label>
              <Input id="pw" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="ledgerflow-demo" autoComplete="current-password" />
              <p className="mt-1 text-[11.5px] text-ink-3">Shared demo password: <span className="font-mono">ledgerflow-demo</span></p>
            </div>
            {error && <p className="rounded-md bg-danger-soft px-3 py-2 text-[12.5px] text-danger" role="alert">{error}</p>}
            <Button variant="primary" className="w-full" size="lg" loading={busy} type="submit">
              Sign in <ArrowRight />
            </Button>
          </form>
        </Card>
      </div>
      <p className="pb-5 text-center text-[11.5px] text-ink-3">LedgerFlow · case-study build · demo authentication, not production identity</p>
    </div>
  );
}

export default function LoginPage() {
  return <React.Suspense><LoginForm /></React.Suspense>;
}
