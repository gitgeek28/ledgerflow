"use client";
import { ChevronLeft, ChevronRight, Download, Minus, Plus, RotateCcw } from "lucide-react";
import * as React from "react";
import { Document, Page, pdfjs } from "react-pdf";

import { cn } from "@/lib/utils";

pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

export type Highlight = { page: number; bbox?: number[] | null; label?: string } | null;

export default function PdfViewer({ url, highlight, className }: { url: string; highlight?: Highlight; className?: string }) {
  const [pages, setPages] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [zoom, setZoom] = React.useState(1);
  const [width, setWidth] = React.useState(560);
  const [natural, setNatural] = React.useState<{ w: number; h: number } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const box = React.useRef<HTMLDivElement>(null);
  const hlRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(Math.max(280, el.clientWidth - 32)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  React.useEffect(() => {
    if (highlight?.page) setPage(highlight.page);
  }, [highlight]);

  React.useEffect(() => {
    hlRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlight, natural, page]);

  const renderWidth = width * zoom;
  const scale = natural ? renderWidth / natural.w : 1;
  const hl = highlight && highlight.page === page && highlight.bbox && natural ? highlight.bbox : null;

  return (
    <div className={cn("flex h-full flex-col", className)}>
      <div className="flex items-center gap-1 border-b border-line bg-surface-2 px-2 py-1.5">
        <button aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
          className="rounded p-1 text-ink-2 hover:bg-surface-3 disabled:opacity-40"><ChevronLeft className="size-4" /></button>
        <span className="num min-w-[70px] text-center text-[12px] text-ink-2">Page {page} / {pages || "–"}</span>
        <button aria-label="Next page" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}
          className="rounded p-1 text-ink-2 hover:bg-surface-3 disabled:opacity-40"><ChevronRight className="size-4" /></button>
        <div className="mx-1 h-4 w-px bg-line" />
        <button aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(0.6, +(z - 0.15).toFixed(2)))}
          className="rounded p-1 text-ink-2 hover:bg-surface-3"><Minus className="size-4" /></button>
        <span className="num w-11 text-center text-[12px] text-ink-2">{Math.round(zoom * 100)}%</span>
        <button aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(2.5, +(z + 0.15).toFixed(2)))}
          className="rounded p-1 text-ink-2 hover:bg-surface-3"><Plus className="size-4" /></button>
        <button aria-label="Reset zoom" onClick={() => setZoom(1)} className="rounded p-1 text-ink-2 hover:bg-surface-3"><RotateCcw className="size-3.5" /></button>
        <div className="flex-1" />
        {highlight?.label && <span className="truncate text-[11.5px] text-accent">Showing evidence: {highlight.label}</span>}
        <a href={url} target="_blank" rel="noreferrer" aria-label="Open original PDF"
          className="rounded p-1 text-ink-2 hover:bg-surface-3"><Download className="size-4" /></a>
      </div>
      <div ref={box} className="flex-1 overflow-auto bg-surface-3 p-4">
        {error ? (
          <p className="p-6 text-center text-[13px] text-ink-3">{error}</p>
        ) : (
          <Document file={url} onLoadSuccess={(d) => { setPages(d.numPages); setError(null); }}
            onLoadError={() => setError("This document cannot be rendered in the browser (the file may be damaged). The original is still stored and downloadable.")}
            loading={<div className="lf-pulse mx-auto h-[600px] max-w-[560px] rounded bg-surface" />}>
            <div className="relative mx-auto w-fit shadow-card">
              <Page pageNumber={page} width={renderWidth} renderTextLayer={false} renderAnnotationLayer={false}
                onLoadSuccess={(p) => setNatural({ w: p.originalWidth, h: p.originalHeight })} />
              {hl && (
                <div ref={hlRef} aria-hidden className="pointer-events-none absolute rounded-[3px] ring-2 ring-accent"
                  style={{ left: hl[0] * scale - 3, top: hl[1] * scale - 3, width: (hl[2] - hl[0]) * scale + 6,
                    height: (hl[3] - hl[1]) * scale + 6, background: "var(--highlight)" }} />
              )}
            </div>
          </Document>
        )}
      </div>
    </div>
  );
}
