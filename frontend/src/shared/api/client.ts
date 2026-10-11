import createClient from "openapi-fetch"
import type { paths } from "./schema.gen"
export const api = createClient<paths>({ baseUrl: "/api" })
export class ApiError extends Error {
  constructor(readonly code: string) {
    super(code)
  }
}
export function unwrap<T>(result: { data?: T; error?: unknown; response?: Response }): T {
  if (result.error) throw new ApiError(String(result.response?.status ?? "unknown"))
  if (!result.data) throw new ApiError("unknown")
  return result.data
}
