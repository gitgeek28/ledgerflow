"use client";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, Copy, FileUp, FileText, Info, Loader2, Play, Trash2, UploadCloud } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/shell";
import { Badge, StatusBadge } from "@/components/status/status";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api/client";
import { useSamples } from "@/lib/api/hooks";
import type { Sample, UploadResult } from "@/lib/api/types";
import { bytes } from "@/lib/format";
import { cn } from "@/lib/utils";

const MAX_MB = 20;
const MAX_FILES = 25;

type Pending = { file: File; error?: string };

function validate(file: File): string | undefined {
  if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") return "Not a PDF";
  if (file.size === 0) return "Empty file";
  if (file.size > MAX_MB * 1024 * 1024) return `Larger than ${MAX_MB} MB`;
  return undefined;
}

function ResultRow({ r }: { r: UploadResult }) {
  const icon = r.outcome === "CREATED" ? <CheckCircle2 className="size-4 text-success" /> :
    r.outcome === "DUPLICATE_FILE" ? <Copy className="size-4 text-warning" /> : <CircleAlert className="size-4 text-danger" />;
  return (
    <li className="flex items-start gap-3 border-b border-line px-4 py-2.5 last:border-0">
      <span className="mt-0.5">{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="truncate text-[13px] font-medium">{r.filename}</span>
          {r.outcome === "DUPLICATE_FILE" && <Badge tone="warning">Exact duplicate file</Badge>}
          {r.outcome === "REJECTED" && <Badge tone="danger">{r.error_code ?? "Rejected"}</Badge>}
        </div>
        <p className="text-[12.5px] text-ink-2">{r.message}</p>
      </div>
      {r.run_id && <Button asChild size="sm" variant="primary"><Link href={`/runs/${r.run_id}`}><Play className="size-3.5" />Live run</Link></Button>}
      {r.outcome === "DUPLICATE_FILE" && r.invoice_id &&
        <Button asChild size="sm"><Link href={`/invoices/${r.invoice_id}`}>Open {r.reference}</Link></Button>}
    </li>
  );
}

export default function IntakePage() {
  const router = useRouter();
  const qc = useQueryClient();
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [pending, setPending] = React.useState<Pending[]>([]);
  const [dragging, setDragging] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [results, setResults] = React.useState<UploadResult[]>([]);
  const [follow, setFollow] = React.useState(true);
  const { data: samples } = useSamples();

  function add(files: FileList | File[]) {
    const list = Array.from(files).map((file) => ({ file, error: validate(file) }));
    setPending((p) => [...p, ...list].slice(0, MAX_FILES));
  }

  async function send(files: File[], label: string) {
    setBusy(label);
    try {
      let out: UploadResult[];
      if (files.length === 1) {
        const fd = new FormData();
        fd.append("file", files[0]);
        out = [await api.upload<UploadResult>("/invoices", fd)];
      } else {
        const fd = new FormData();
        files.forEach((f) => fd.append("files", f));
        out = (await api.upload<{ results: UploadResult[] }>("/invoices/batch", fd)).results;
      }
      setResults((r) => [...out, ...r]);
      qc.invalidateQueries({ queryKey: ["invoices"] });
      const created = out.filter((r) => r.outcome === "CREATED");
      if (follow && files.length === 1 && created[0]?.run_id) router.push(`/runs/${created[0].run_id}`);
      else toast.success(`${created.length} of ${out.length} file(s) accepted for processing`);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Upload failed";
      setResults((r) => [{ filename: files.map((f) => f.name).join(", "), outcome: "REJECTED", invoice_id: null,
        reference: null, run_id: null, message: msg, error_code: e instanceof ApiError ? e.code : null }, ...r]);
    } finally {
      setBusy(null);
    }
  }

  async function uploadPending() {
    const ok = pending.filter((p) => !p.error).map((p) => p.file);
    if (!ok.length) return;
    await send(ok, "files");
    setPending([]);
  }

  async function sampleFiles(list: Sample[]): Promise<File[]> {
    return Promise.all(list.map(async (s) => {
      const res = await fetch(`/api/samples/${s.id}/file`, { credentials: "include" });
      if (!res.ok) throw new Error(`Could not fetch sample ${s.id}`);
      return new File([await res.blob()], s.filename, { type: "application/pdf" });
    }));
  }

  async function uploadSamples(list: Sample[], label: string) {
    try { await send(await sampleFiles(list), label); } catch (e) { toast.error((e as Error).message); setBusy(null); }
  }

  const demo = (samples ?? []).filter((s) => s.group === "demo");
  const history = (samples ?? []).filter((s) => s.group === "history");
  const valid = pending.filter((p) => !p.error).length;

  return (
    <div className="mx-auto max-w-[1280px]">
      <PageHeader crumbs={[{ href: "/invoices", label: "Invoices" }, { label: "Upload" }]} title="Upload invoices"
        description="PDF only, up to 20 MB and 25 files per batch. Machine-readable and scanned PDFs are supported." />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="space-y-5">
          <Card>
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); add(e.dataTransfer.files); }}
              className={cn("m-4 flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-12 text-center transition-colors",
                dragging ? "border-accent bg-accent-soft" : "border-line-strong bg-surface-2")}>
              <UploadCloud className="size-8 text-ink-3" />
              <p className="mt-3 text-[14px] font-medium">Drop invoice PDFs here</p>
              <p className="mt-1 text-[12.5px] text-ink-3">Files are stored under a server-generated key; the original filename is kept only as metadata.</p>
              <Button className="mt-4" onClick={() => inputRef.current?.click()}><FileUp />Choose files</Button>
              <input ref={inputRef} type="file" accept="application/pdf,.pdf" multiple hidden
                onChange={(e) => { if (e.target.files) add(e.target.files); e.target.value = ""; }} />
            </div>
            {pending.length > 0 && (
              <div className="border-t border-line">
                <ul>
                  {pending.map((p, i) => (
                    <li key={`${p.file.name}-${i}`} className="flex items-center gap-3 border-b border-line px-4 py-2 last:border-0">
                      <FileText className="size-4 text-ink-3" />
                      <span className="min-w-0 flex-1 truncate text-[13px]">{p.file.name}</span>
                      <span className="num text-[12px] text-ink-3">{bytes(p.file.size)}</span>
                      {p.error ? <Badge tone="danger">{p.error}</Badge> : <Badge tone="success">Ready</Badge>}
                      <button aria-label={`Remove ${p.file.name}`} onClick={() => setPending((x) => x.filter((_, j) => j !== i))}
                        className="rounded p-1 text-ink-3 hover:bg-surface-3"><Trash2 className="size-4" /></button>
                    </li>
                  ))}
                </ul>
                <div className="flex flex-wrap items-center justify-between gap-3 bg-surface-2 px-4 py-3">
                  <label className="flex items-center gap-2 text-[12.5px] text-ink-2">
                    <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />
                    Open the live run when uploading a single file
                  </label>
                  <div className="flex gap-2">
                    <Button variant="ghost" onClick={() => setPending([])}>Clear</Button>
                    <Button variant="primary" onClick={uploadPending} disabled={!valid} loading={busy === "files"}>
                      Upload {valid} file{valid === 1 ? "" : "s"}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </Card>

          <Card>
            <CardHeader title="Submissions this session" description="Each accepted file starts a real processing run." />
            {results.length === 0 ? (
              <p className="px-4 py-6 text-center text-[13px] text-ink-3">Nothing uploaded yet.</p>
            ) : <ul>{results.map((r, i) => <ResultRow key={i} r={r} />)}</ul>}
          </Card>
        </div>

        <Card className="self-start">
          <CardHeader title="Sample invoices" description="Synthetic PDFs from the scenario catalogue. Uploading one sends the actual file through the same intake path." />
          <div className="max-h-[70vh] overflow-y-auto">
            <div className="flex items-center justify-between gap-2 border-b border-line bg-surface-2 px-4 py-2.5">
              <div className="text-[12px] text-ink-2"><span className="font-medium text-ink">History set</span> · {history.length} invoices that seed prior activity (originals for duplicates, earlier split invoices)</div>
              <Button size="sm" onClick={() => uploadSamples(history, "history")} loading={busy === "history"} disabled={!history.length}>Upload all</Button>
            </div>
            <ul>
              {demo.map((s) => (
                <li key={s.id} className="border-b border-line px-4 py-2.5 last:border-0">
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 rounded bg-surface-3 px-1.5 font-mono text-[11px] text-ink-2">{s.id}</span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] font-medium">{s.title}</div>
                      <p className="mt-0.5 line-clamp-2 text-[12px] text-ink-3">{s.description}</p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        {s.expected_status && <span className="inline-flex items-center gap-1 text-[11.5px] text-ink-3">expected <StatusBadge status={s.expected_status} /></span>}
                        {s.prerequisites.filter((p) => p !== "S01").length > 0 && (
                          <span className="inline-flex items-center gap-1 text-[11.5px] text-ink-3"><Info className="size-3" />needs {s.prerequisites.join(", ")} first</span>
                        )}
                        {s.id === "S02" && <span className="text-[11.5px] text-ink-3">re-uploads the S01 file</span>}
                      </div>
                    </div>
                    <Button size="sm" variant="secondary" aria-label={`Upload sample ${s.id}`}
                      onClick={() => uploadSamples([s.id === "S02" ? { ...s, id: "S01" } : s], s.id)} disabled={!!busy}>
                      {busy === s.id ? <Loader2 className="size-3.5 animate-spin" /> : <FileUp className="size-3.5" />}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </div>
    </div>
  );
}
