import type { Characteristic } from "@/entities/rag"

export type KtruBand = Characteristic["bands"][number]
export interface Band {
  readonly option: string
  readonly label: string
}
export type FieldKind =
  | { readonly type: "boolean"; readonly yes: string; readonly no: string }
  | { readonly type: "input"; readonly unit: string; readonly bands: readonly KtruBand[] }
  | { readonly type: "range"; readonly unit: string; readonly bands: readonly Band[] }
  | { readonly type: "number"; readonly unit: string; readonly bands: readonly Band[] }
  | { readonly type: "search" }
  | { readonly type: "choice" }

const YES = "\u0434\u0430"
const NO = "\u043d\u0435\u0442"
const NUMBER = /^(-?\d+(?:\.\d+)?)\s*(.*)$/
const SEARCH_FROM = 13
const INPUT_FROM = 5

export function bandLabel(band: KtruBand, format: (value: number) => string) {
  if (band.min !== null && band.max !== null) return `${format(band.min)}–${format(band.max)}`
  if (band.min !== null) return `${band.min_inclusive ? "≥" : ">"} ${format(band.min)}`
  if (band.max !== null) return `${band.max_inclusive ? "≤" : "<"} ${format(band.max)}`
  return band.option
}

function contains(band: KtruBand, value: number) {
  if (band.min !== null && (value < band.min || (value === band.min && !band.min_inclusive)))
    return false
  if (band.max !== null && (value > band.max || (value === band.max && !band.max_inclusive)))
    return false
  return true
}

function width(band: KtruBand) {
  const low = band.min ?? Number.NEGATIVE_INFINITY
  const high = band.max ?? Number.POSITIVE_INFINITY
  return [high - low, -low, high] as const
}

export function matchBand(bands: readonly KtruBand[], value: number) {
  let best: KtruBand | null = null
  for (const band of bands) {
    if (!contains(band, value)) continue
    if (!best) {
      best = band
      continue
    }
    const [a, b] = [width(band), width(best)]
    const index = a.findIndex((item, i) => item !== b[i])
    if (index >= 0 && (a[index] ?? 0) < (b[index] ?? 0)) best = band
  }
  return best
}

export type Doubt = NonNullable<Characteristic["warning"]>
const SPREAD = 10

export function doubt(bands: readonly KtruBand[], value: number) {
  const edges = bands.flatMap((band) => [band.min, band.max]).filter((edge) => edge !== null)
  if (!edges.length) return null
  const low = Math.min(...edges)
  const high = Math.max(...edges)
  if (value < 0 && low >= 0) return { code: "negative" as Doubt, edge: low }
  if (high > 0 && value > SPREAD * high) return { code: "large" as Doubt, edge: high }
  if (low > 0 && value > 0 && value < low / SPREAD) return { code: "small" as Doubt, edge: low }
  return null
}

function concrete(options: readonly string[]) {
  const parsed = options.map((option) => NUMBER.exec(option.trim()))
  if (parsed.some((match) => !match?.[1])) return null
  const units = new Set(parsed.map((match) => (match?.[2] ?? "").trim()))
  if (units.size !== 1) return null
  return {
    unit: [...units][0] ?? "",
    bands: parsed
      .flatMap((match, index) =>
        match?.[1]
          ? [{ option: options[index] ?? "", label: match[1], order: Number(match[1]) }]
          : [],
      )
      .sort((a, b) => a.order - b.order),
  }
}

export function fieldKind(field: Characteristic, format: (value: number) => string): FieldKind {
  const { options, multiple } = field
  const lower = options.map((option) => option.trim().toLowerCase())
  if (!multiple && options.length === 2 && lower.includes(YES) && lower.includes(NO))
    return {
      type: "boolean",
      yes: options[lower.indexOf(YES)] ?? YES,
      no: options[lower.indexOf(NO)] ?? NO,
    }
  if (field.bands.length > 0) {
    const unit = field.unit ?? ""
    if (!multiple && field.bands.length >= INPUT_FROM)
      return { type: "input", unit, bands: field.bands }
    const bands = field.bands.map((band) => ({
      option: band.option,
      label: bandLabel(band, format),
    }))
    return { type: "range", unit, bands }
  }
  if (options.length > 1) {
    const numbers = concrete(options)
    if (numbers) return { type: "number", ...numbers }
  }
  return options.length >= SEARCH_FROM ? { type: "search" } : { type: "choice" }
}

export function toggle(values: readonly string[], option: string, multiple: boolean): string[] {
  if (values.includes(option)) return values.filter((value) => value !== option)
  return multiple ? [...values, option] : [option]
}
