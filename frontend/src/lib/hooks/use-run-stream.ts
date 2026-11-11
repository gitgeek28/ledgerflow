"use client";
import * as React from "react";

import { api } from "@/lib/api/client";
import type { RunEvent } from "@/lib/api/types";

export type StreamState = "connecting" | "live" | "polling" | "ended" | "error";

/**
 * Subscribes to the persisted run events over Server-Sent Events.
 * - Events are de-duplicated by id, so reconnects never duplicate timeline entries.
 * - EventSource resends Last-Event-ID automatically on reconnect; the server resumes after it.
 * - If the stream cannot be (re)established, falls back to polling /events?after=<last id>.
 */
export function useRunStream(runId: string, onEnd?: () => void) {
  const [events, setEvents] = React.useState<RunEvent[]>([]);
  const [state, setState] = React.useState<StreamState>("connecting");
  const lastId = React.useRef(0);
  const onEndRef = React.useRef(onEnd);
  onEndRef.current = onEnd;

  const merge = React.useCallback((incoming: RunEvent[]) => {
    if (!incoming.length) return;
    setEvents((prev) => {
      const seen = new Set(prev.map((e) => e.id));
      const fresh = incoming.filter((e) => !seen.has(e.id));
      if (!fresh.length) return prev;
      const next = [...prev, ...fresh].sort((a, b) => a.id - b.id);
      lastId.current = next[next.length - 1].id;
      return next;
    });
  }, []);

  React.useEffect(() => {
    setEvents([]);
    lastId.current = 0;
    setState("connecting");
    let closed = false;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;

    const poll = async () => {
      if (closed) return;
      try {
        const batch = await api.get<RunEvent[]>(`/runs/${runId}/events`, { after: lastId.current });
        merge(batch);
        const done = batch.some((e) => e.event_type === "RUN_COMPLETED" || e.event_type === "RUN_FAILED");
        if (done) { setState("ended"); onEndRef.current?.(); return; }
      } catch { /* keep polling */ }
      pollTimer = setTimeout(poll, 1200);
    };

    const es = new EventSource(`/api/runs/${runId}/events/stream?after=0`, { withCredentials: true });
    es.addEventListener("open", () => { failures = 0; setState("live"); });
    es.addEventListener("run_event", (msg) => {
      try { merge([JSON.parse((msg as MessageEvent).data) as RunEvent]); } catch { /* ignore malformed */ }
    });
    es.addEventListener("end", () => { es.close(); setState("ended"); onEndRef.current?.(); });
    es.addEventListener("error", () => {
      if (closed || es.readyState === EventSource.CLOSED) {
        failures += 1;
      } else {
        failures += 1; // browser is retrying; after a few attempts fall back to polling
      }
      if (failures >= 3 && !closed) {
        es.close();
        setState("polling");
        poll();
      }
    });
    return () => { closed = true; es.close(); if (pollTimer) clearTimeout(pollTimer); };
  }, [runId, merge]);

  return { events, state };
}
