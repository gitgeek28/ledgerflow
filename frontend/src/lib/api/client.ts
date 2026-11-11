export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown,
              public requestId?: string) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | null | undefined | (string | number)[]>;

export function qs(params?: Query): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, String(x)));
    else sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function handle<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const body = text ? safeJson(text) : null;
  if (!res.ok) {
    const err = body?.error;
    if (res.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
    throw new ApiError(res.status, err?.code ?? "HTTP_ERROR", err?.message ?? res.statusText, err?.details,
      err?.request_id);
  }
  return body as T;
}

function safeJson(text: string) {
  try { return JSON.parse(text); } catch { return null; }
}

export const api = {
  get: <T>(path: string, params?: Query) =>
    fetch(`/api${path}${qs(params)}`, { credentials: "include", cache: "no-store" }).then((r) => handle<T>(r)),
  post: <T>(path: string, body?: unknown) =>
    fetch(`/api${path}`, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body),
    }).then((r) => handle<T>(r)),
  upload: <T>(path: string, form: FormData) =>
    fetch(`/api${path}`, { method: "POST", credentials: "include", body: form }).then((r) => handle<T>(r)),
};
