import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { api, unwrap } from "@/shared/api/client"
import type { components } from "@/shared/api/schema.gen"

export type CatalogFound = components["schemas"]["CatalogFound"]
export type CatalogComparison = components["schemas"]["CatalogComparison"]
export type ComparisonRow = components["schemas"]["ComparisonRow"]
export type FindMode = "text" | "semantic"

export function useCatalogFind(text: string, mode: FindMode) {
  const q = text.trim()
  return useQuery({
    queryKey: ["catalog-find", mode, q],
    enabled: q.length >= 2,
    placeholderData: keepPreviousData,
    staleTime: Number.POSITIVE_INFINITY,
    retry: mode === "text" ? 3 : 0,
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/catalog", { params: { query: { q, mode } }, signal })),
  })
}

export function useCatalogComparison(codes: readonly string[]) {
  return useQuery({
    queryKey: ["catalog-comparison", ...codes],
    enabled: codes.length >= 2,
    placeholderData: keepPreviousData,
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/catalog/compare", {
          params: { query: { codes: [...codes] } },
          signal,
        }),
      ),
  })
}
