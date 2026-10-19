export type Row = Record<string, any>;
// Public origin only: Vite variables are bundled into the browser, never secrets.
export const API_ORIGIN = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
export const sampleUrl = (name: string) => `${API_ORIGIN}/samples/${name}`;
export type Filters = {
  start: string;
  end: string;
  store_id?: number;
  category_id?: number;
  brand_id?: number;
  sku_id?: number;
};
export const initialFilters: Filters = {
  start: "2026-09-19",
  end: "2026-10-18",
};
export function params(filters: Filters) {
  return new URLSearchParams(
    Object.entries(filters)
      .filter(([, v]) => v !== undefined && v !== "")
      .map(([k, v]) => [k, String(v)]),
  ).toString();
}
export async function api<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${localStorage.getItem("rp-token") ?? ""}`,
  };
  if (options.body && !(options.body instanceof FormData))
    headers["Content-Type"] = "application/json";
  const r = await fetch(API_ORIGIN + "/api/v1" + path, {
    ...options,
    headers: { ...headers, ...options.headers },
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  }
  return r.json();
}
export async function fileDownload(path: string, name: string) {
  const r = await fetch(API_ORIGIN + "/api/v1" + path, {
    headers: {
      Authorization: `Bearer ${localStorage.getItem("rp-token") ?? ""}`,
    },
  });
  if (!r.ok) throw new Error("Download failed. Please refresh and retry.");
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const money = (v: number = 0) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(v);
export const compactMoney = (v: number = 0) =>
  v >= 10000000
    ? `₹${(v / 10000000).toFixed(2)} Cr`
    : v >= 100000
      ? `₹${(v / 100000).toFixed(2)} L`
      : money(v);
export const num = (v: number = 0) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 }).format(v);
