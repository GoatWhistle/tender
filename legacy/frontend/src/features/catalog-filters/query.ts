import type { Sort } from "../../api";

export const SORTS: readonly Sort[] = ["relevance", "price_asc", "price_desc", "filled"];

export function readFilters(params: URLSearchParams): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const f of params.getAll("f")) {
    const [ch, v] = f.split(":");
    if (ch && v) (out[ch] ??= []).push(v);
  }
  return out;
}

export function readSort(params: URLSearchParams): Sort {
  const sort = params.get("sort");
  return SORTS.find((s) => s === sort) ?? "relevance";
}

export function toggleFilter(params: URLSearchParams, characteristic: string, value: string) {
  const key = `${characteristic}:${value}`;
  const all = params.getAll("f");
  params.delete("f");
  for (const f of all.includes(key) ? all.filter((x) => x !== key) : [...all, key])
    params.append("f", f);
}

export function setFacet(params: URLSearchParams, characteristic: string, values: string[]) {
  const rest = params.getAll("f").filter((f) => !f.startsWith(`${characteristic}:`));
  params.delete("f");
  for (const f of [...rest, ...values.map((v) => `${characteristic}:${v}`)]) params.append("f", f);
}
