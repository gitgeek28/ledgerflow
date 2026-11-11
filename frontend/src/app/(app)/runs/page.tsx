"use client";
import { PlayCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { PageHeader } from "@/components/layout/shell";
import { RunStatusBadge, StatusBadge } from "@/components/status/status";
import { Segmented } from "@/components/ui/overlays";
import { Card, EmptyState, ErrorState } from "@/components/ui/primitives";
import { Pagination, SkeletonRows, SortTh, Table, Td, THead, Tr } from "@/components/ui/table";
import { useRuns } from "@/lib/api/hooks";
import { ago, ms } from "@/lib/format";

type Filter = "ALL" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
const TRIGGER: Record<string, string> = { UPLOAD: "Upload", RETRY: "Retry", REEVALUATION: "Re-evaluation" };

export default function RunsPage() {
  const router = useRouter();
  const [status, setStatus] = React.useState<Filter>("ALL");
  const [page, setPage] = React.useState(1);
  const [sort, setSort] = React.useState("created_at");
  const [order, setOrder] = React.useState("desc");
  React.useEffect(() => setPage(1), [status, sort, order]);
  const { data, isLoading, isError, error, refetch } = useRuns({ status: status === "ALL" ? undefined : status, page, sort, order });
  const onSort = (f: string) => { if (f === sort) setOrder(order === "asc" ? "desc" : "asc"); else { setSort(f); setOrder(f === "created_at" ? "desc" : "asc"); } };
  const sp = { sort, order, onSort };

  return (
    <div>
      <PageHeader title="Processing runs"
        description="Each run is one execution of the workflow for an invoice. Retries and re-evaluations after a review action create new runs; earlier runs are kept." />
      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
          <Segmented<Filter> value={status} onChange={setStatus} options={[
            { value: "ALL", label: "All" }, { value: "QUEUED", label: "Queued" }, { value: "RUNNING", label: "Running" },
            { value: "COMPLETED", label: "Completed" }, { value: "FAILED", label: "Failed" }]} />
          <span className="ml-auto text-[12px] text-ink-3">Refreshes automatically</span>
        </div>
        {isError ? (
          <div className="p-3"><ErrorState error={error} onRetry={() => refetch()} /></div>
        ) : (
          <>
            <Table>
              <THead>
                <tr>
                  <SortTh label="Run" field="attempt" {...sp} /><SortTh label="Invoice" field="invoice" {...sp} />
                  <SortTh label="Vendor" field="vendor" {...sp} /><SortTh label="Trigger" field="trigger" {...sp} />
                  <SortTh label="Status" field="status" {...sp} /><SortTh label="Decision" field="decision" {...sp} />
                  <SortTh label="Processing" field="duration_ms" align="right" {...sp} />
                  <SortTh label="Started" field="created_at" {...sp} /><SortTh label="Extractor" field="extractor" {...sp} />
                </tr>
              </THead>
              <tbody>
                {isLoading ? <SkeletonRows rows={10} cols={9} /> : (data?.items ?? []).map((r) => (
                  <Tr key={r.id} onClick={() => router.push(`/runs/${r.id}`)}>
                    <Td className="whitespace-nowrap">
                      <span className="font-mono text-[12px] text-ink">{r.id.slice(0, 8)}</span>
                      <span className="ml-1.5 text-[12px] text-ink-3">#{r.attempt}</span>
                    </Td>
                    <Td className="max-w-[240px]">
                      <div className="font-medium">{r.invoice_reference ?? "—"}</div>
                      <div className="truncate text-[12px] text-ink-3" title={r.invoice_filename ?? undefined}>{r.invoice_filename}</div>
                    </Td>
                    <Td className="max-w-[200px] truncate text-ink-2">{r.vendor_name ?? "—"}</Td>
                    <Td className="whitespace-nowrap text-ink-2">{TRIGGER[r.trigger] ?? r.trigger}</Td>
                    <Td><RunStatusBadge status={r.status} /></Td>
                    <Td>{r.decision ? <StatusBadge status={r.decision} /> :
                      r.status === "FAILED" ? <span className="text-[12px] text-ink-3">{r.error_code}</span> :
                        <span className="text-ink-3">—</span>}</Td>
                    <Td align="right">{ms(r.duration_ms)}</Td>
                    <Td className="whitespace-nowrap text-ink-2">{ago(r.started_at ?? r.created_at)}</Td>
                    <Td className="max-w-[200px]">
                      <span className="block truncate text-[12px] text-ink-3" title={r.extractor ?? undefined}>{r.extractor ?? "—"}</span>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
            {!isLoading && data && data.items.length === 0 && (
              <EmptyState icon={<PlayCircle />} title="No runs yet"
                description="Upload an invoice to start a processing run. Every stage it executes is recorded here." />
            )}
            {data && data.total > 0 && (
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            )}
          </>
        )}
      </Card>
    </div>
  );
}
