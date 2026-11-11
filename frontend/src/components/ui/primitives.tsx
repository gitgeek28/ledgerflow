import * as React from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-[10px] border border-line bg-surface shadow-card", className)} {...p} />;
}

export function CardHeader({ title, description, action, className }: { title: React.ReactNode;
  description?: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-4 border-b border-line px-4 py-3", className)}>
      <div className="min-w-0">
        <h3 className="text-[13px] font-semibold text-ink">{title}</h3>
        {description && <p className="mt-0.5 text-[12px] text-ink-3">{description}</p>}
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </div>
  );
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...p }, ref) => (
    <input ref={ref} className={cn(
      "h-8 w-full rounded-md border border-line-strong bg-surface px-2.5 text-[13px] text-ink placeholder:text-ink-3",
      "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 disabled:opacity-60", className)} {...p} />
  ));
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...p }, ref) => (
    <textarea ref={ref} className={cn(
      "w-full rounded-md border border-line-strong bg-surface px-2.5 py-2 text-[13px] text-ink placeholder:text-ink-3",
      "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20", className)} {...p} />
  ));
Textarea.displayName = "Textarea";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...p }, ref) => (
    <select ref={ref} className={cn(
      "h-8 rounded-md border border-line-strong bg-surface pl-2.5 pr-7 text-[13px] text-ink",
      "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20", className)} {...p}>
      {children}
    </select>
  ));
Select.displayName = "Select";

export function Label({ className, ...p }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("mb-1 block text-[12px] font-medium text-ink-2", className)} {...p} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("lf-pulse rounded-md bg-surface-3", className)} />;
}

export function EmptyState({ icon, title, description, action, className }: { icon?: React.ReactNode;
  title: string; description?: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-12 text-center", className)}>
      {icon && <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-surface-3 text-ink-3 [&_svg]:size-5">{icon}</div>}
      <p className="text-[14px] font-medium text-ink">{title}</p>
      {description && <p className="mt-1 max-w-md text-[13px] text-ink-3">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-danger/30 bg-danger-soft px-4 py-3 text-[13px] text-danger">
      <span>Could not load data: {message}</span>
      {onRetry && <button onClick={onRetry} className="font-medium underline underline-offset-2">Retry</button>}
    </div>
  );
}

export function Kv({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <dt className="text-[11.5px] font-medium uppercase tracking-wide text-ink-3">{label}</dt>
      <dd className="mt-0.5 truncate text-[13px] text-ink">{children}</dd>
    </div>
  );
}

export function SectionTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h4 className={cn("text-[11.5px] font-semibold uppercase tracking-wide text-ink-3", className)}>{children}</h4>;
}

export function Mono({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("font-mono text-[12px]", className)}>{children}</span>;
}
