"use client";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  AuditEvent, DashboardSummary, InvoiceDetail, InvoiceListItem, Page, PODetail, Policy, PurchaseOrder,
  Readiness, ReasonCode, Run, RunDetail, RunEvent, Sample, User, Vendor,
} from "./types";

export const keys = {
  me: ["me"] as const,
  invoice: (id: string) => ["invoice", id] as const,
  invoices: (p: object) => ["invoices", p] as const,
  run: (id: string) => ["run", id] as const,
};

export const useMe = () => useQuery({ queryKey: keys.me, queryFn: () => api.get<User>("/auth/me"), retry: false,
  staleTime: 5 * 60_000 });
export const useDemoUsers = () => useQuery({ queryKey: ["demo-users"], queryFn: () => api.get<User[]>("/auth/demo-users") });
export const useReadiness = () => useQuery({ queryKey: ["ready"], queryFn: () => api.get<Readiness>("/health/ready"),
  refetchInterval: 15_000 });

export const useDashboard = (days: number) => useQuery({
  queryKey: ["dashboard", days], queryFn: () => api.get<DashboardSummary>("/dashboard/summary", { days }),
  refetchInterval: 10_000, placeholderData: keepPreviousData });

export type InvoiceFilters = { q?: string; status?: string[]; priority?: string; vendor_id?: string;
  date_from?: string; date_to?: string; min_amount?: string; max_amount?: string; sort?: string; order?: string;
  page?: number; page_size?: number };
export const useInvoices = (f: InvoiceFilters) => useQuery({
  queryKey: keys.invoices(f), queryFn: () => api.get<Page<InvoiceListItem>>("/invoices", f),
  placeholderData: keepPreviousData, refetchInterval: 15_000 });

export const useInvoice = (id: string) => useQuery({
  queryKey: keys.invoice(id), queryFn: () => api.get<InvoiceDetail>(`/invoices/${id}`),
  refetchInterval: (q) => (q.state.data?.status === "PROCESSING" ? 1500 : false) });
export const useInvoiceAudit = (id: string) => useQuery({
  queryKey: ["invoice-audit", id], queryFn: () => api.get<AuditEvent[]>(`/invoices/${id}/audit`) });

export const useRuns = (p: { status?: string; page?: number }) => useQuery({
  queryKey: ["runs", p], queryFn: () => api.get<Page<Run>>("/runs", { ...p, page_size: 25 }),
  placeholderData: keepPreviousData, refetchInterval: 5_000 });
export const useRun = (id: string) => useQuery({
  queryKey: keys.run(id), queryFn: () => api.get<RunDetail>(`/runs/${id}`) });
export const useRunEvents = (id: string, enabled: boolean) => useQuery({
  queryKey: ["run-events", id], queryFn: () => api.get<RunEvent[]>(`/runs/${id}/events`), enabled,
  refetchInterval: enabled ? 1500 : false });

export const useReviewQueue = (view: string) => useQuery({
  queryKey: ["queue", view], queryFn: () => api.get<InvoiceListItem[]>("/review-queue", { view }),
  refetchInterval: 10_000 });

export const useVendors = (p: { q?: string; status?: string; page?: number }) => useQuery({
  queryKey: ["vendors", p], queryFn: () => api.get<Page<Vendor>>("/vendors", { ...p, page_size: 50 }),
  placeholderData: keepPreviousData });
export const useVendor = (id: string) => useQuery({
  queryKey: ["vendor", id], queryFn: () => api.get<{ vendor: Vendor; purchase_orders: PurchaseOrder[];
    invoices: InvoiceListItem[]; bank_change_alerts: number }>(`/vendors/${id}`) });
export const usePOs = (p: { q?: string; status?: string; vendor_id?: string; page?: number }) => useQuery({
  queryKey: ["pos", p], queryFn: () => api.get<Page<PurchaseOrder>>("/purchase-orders", { ...p, page_size: 50 }),
  placeholderData: keepPreviousData });
export const usePO = (id: string) => useQuery({ queryKey: ["po", id],
  queryFn: () => api.get<PODetail>(`/purchase-orders/${id}`) });

export const useAudit = (p: { q?: string; actor_type?: string; action?: string; page?: number }) => useQuery({
  queryKey: ["audit", p], queryFn: () => api.get<Page<AuditEvent>>("/audit", { ...p, page_size: 50 }),
  placeholderData: keepPreviousData, refetchInterval: 15_000 });
export const useAuditActions = () => useQuery({ queryKey: ["audit-actions"],
  queryFn: () => api.get<string[]>("/audit/actions") });

export const usePolicies = () => useQuery({ queryKey: ["policies"], queryFn: () => api.get<Policy[]>("/policies") });
export const useReasonCodes = () => useQuery({ queryKey: ["reason-codes"],
  queryFn: () => api.get<ReasonCode[]>("/policies/reason-codes"), staleTime: Infinity });
export const useSamples = () => useQuery({ queryKey: ["samples"], queryFn: () => api.get<Sample[]>("/samples"),
  staleTime: Infinity });

export type ReviewActionBody = { action: string; reason?: string; note?: string; field?: string; value?: string;
  po_id?: string; vendor_id?: string };
export function useReviewAction(invoiceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ReviewActionBody) => api.post<{ invoice_id: string; status: string; run_id: string | null;
      draft: string | null; message: string }>(`/invoices/${invoiceId}/review-actions`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.invoice(invoiceId) });
      qc.invalidateQueries({ queryKey: ["invoice-audit", invoiceId] });
      qc.invalidateQueries({ queryKey: ["queue"] });
      qc.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}
