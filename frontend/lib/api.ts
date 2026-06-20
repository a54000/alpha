const SERVER_API_BASE =
  process.env.API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8000";

const CLIENT_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

export const API_BASE = typeof window === "undefined" ? SERVER_API_BASE : CLIENT_API_BASE;

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

type ApiFetchOptions = RequestInit & {
  next?: {
    revalidate?: number;
  };
};

export async function apiGet<T>(path: string, options?: ApiFetchOptions): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, options || { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    let detail = `API request failed: ${response.status}`;
    try {
      const payload = await response.json();
      if (payload?.detail) detail = String(payload.detail);
    } catch {
      // Keep the status-only error when the API did not return JSON.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function safeApiGet<T>(path: string, options?: ApiFetchOptions): Promise<ApiResult<T>> {
  try {
    const data = await apiGet<T>(path, options);
    return { ok: true, data };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "API request failed"
    };
  }
}

export function money(value: unknown): string {
  if (value === null || value === undefined || value === "") return "n/a";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return number.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export function pct(value: unknown): string {
  if (value === null || value === undefined || value === "") return "n/a";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return `${(number * 100).toFixed(2)}%`;
}

export function relativePoints(value: unknown): string {
  if (value === null || value === undefined || value === "") return "n/a";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  const points = number * 100;
  const sign = points > 0 ? "+" : "";
  return `${sign}${points.toFixed(2)} pts`;
}
