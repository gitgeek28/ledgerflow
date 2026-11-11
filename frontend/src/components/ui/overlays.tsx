"use client";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export function Dialog({ open, onOpenChange, title, description, children, footer, wide }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: React.ReactNode;
  children?: React.ReactNode; footer?: React.ReactNode; wide?: boolean }) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/30 backdrop-blur-[1px]" />
        <DialogPrimitive.Content className={cn(
          "lf-enter fixed left-1/2 top-[12vh] z-50 w-[calc(100vw-32px)] -translate-x-1/2 rounded-2xl border border-line bg-surface shadow-pop",
          wide ? "max-w-2xl" : "max-w-md")}>
          <div className="flex items-start justify-between border-b border-line px-5 py-3.5">
            <div>
              <DialogPrimitive.Title className="text-[14px] font-semibold text-ink">{title}</DialogPrimitive.Title>
              {description && <DialogPrimitive.Description className="mt-0.5 text-[12.5px] text-ink-3">{description}
              </DialogPrimitive.Description>}
            </div>
            <DialogPrimitive.Close className="rounded p-1 text-ink-3 hover:bg-surface-3" aria-label="Close">
              <X className="size-4" />
            </DialogPrimitive.Close>
          </div>
          {children && <div className="max-h-[60vh] overflow-y-auto px-5 py-4">{children}</div>}
          {footer && <div className="flex justify-end gap-2 rounded-b-2xl border-t border-line bg-surface-2 px-5 py-3">{footer}</div>}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export const Tabs = TabsPrimitive.Root;
export function TabsList({ className, ...p }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return <TabsPrimitive.List className={cn("flex items-center gap-1 border-b border-line px-4", className)} {...p} />;
}
export function TabsTrigger({ className, ...p }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return <TabsPrimitive.Trigger className={cn(
    "relative -mb-px inline-flex h-11 items-center gap-1.5 border-b-2 border-transparent px-3 text-[13px] text-ink-3 transition-colors hover:text-ink",
    "data-[state=active]:border-accent data-[state=active]:font-medium data-[state=active]:text-ink", className)} {...p} />;
}
export const TabsContent = TabsPrimitive.Content;

export function Tip({ content, children, side = "top" }: { content: React.ReactNode; children: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right" }) {
  return (
    <TooltipPrimitive.Root delayDuration={200}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content side={side} sideOffset={6}
          className="z-50 max-w-xs rounded-md bg-ink px-2.5 py-1.5 text-[12px] leading-snug text-bg shadow-lg">
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
export const TooltipProvider = TooltipPrimitive.Provider;

export function Segmented<T extends string>({ value, onChange, options, className }: { value: T;
  onChange: (v: T) => void; options: { value: T; label: React.ReactNode; count?: number }[]; className?: string }) {
  return (
    <div role="tablist" className={cn("inline-flex rounded-full border border-line bg-surface-3 p-1", className)}>
      {options.map((o) => (
        <button key={o.value} role="tab" aria-selected={value === o.value} onClick={() => onChange(o.value)}
          className={cn("inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-[12.5px] text-ink-2 transition-all hover:text-ink",
            value === o.value && "bg-surface font-medium text-ink shadow-card")}>
          {o.label}
          {o.count !== undefined && <span className="num rounded bg-line px-1 text-[11px] text-ink-2">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}
