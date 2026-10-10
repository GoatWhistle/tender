export interface Band {
  readonly option: string
  readonly label: string
  readonly order: number
}
export type FieldKind =
  | { readonly type: "boolean"; readonly yes: string; readonly no: string }
  | { readonly type: "range"; readonly unit: string; readonly bands: readonly Band[] }
  | { readonly type: "number"; readonly unit: string; readonly bands: readonly Band[] }
  | { readonly type: "search" }
  | { readonly type: "choice" }

const YES = "\u0434\u0430"
const NO = "\u043d\u0435\u0442"
const BOUNDS = /^(?:([≥>])\s*(-?\d+(?:\.\d+)?))?\s*(?:([≤<])\s*(-?\d+(?:\.\d+)?))?\s*(.*)$/
const NUMBER = /^(-?\d+(?:\.\d+)?)\s*(.*)$/
const SEARCH_FROM = 13

function range(option: string) {
  const match = BOUNDS.exec(option.trim())
  if (!match || (match[2] === undefined && match[4] === undefined)) return null
  const [, lowOp, low, highOp, high, unit = ""] = match
  const label =
    low !== undefined && high !== undefined
      ? `${low}–${high}`
      : low !== undefined
        ? `${lowOp} ${low}`
        : `${highOp} ${high}`
  const order = low !== undefined ? Number(low) : Number(high) - Number.EPSILON
  return { unit: unit.trim(), band: { option, label, order } }
}

function number(option: string) {
  const match = NUMBER.exec(option.trim())
  if (!match?.[1]) return null
  return {
    unit: (match[2] ?? "").trim(),
    band: { option, label: match[1], order: Number(match[1]) },
  }
}

function scale(options: readonly string[], parse: typeof range) {
  const parsed = options.map(parse)
  if (parsed.some((item) => item === null)) return null
  const units = new Set(parsed.map((item) => item?.unit))
  if (units.size !== 1) return null
  return {
    unit: parsed[0]?.unit ?? "",
    bands: parsed.flatMap((item) => (item ? [item.band] : [])).sort((a, b) => a.order - b.order),
  }
}

export function fieldKind(options: readonly string[], multiple: boolean): FieldKind {
  const lower = options.map((option) => option.trim().toLowerCase())
  if (!multiple && options.length === 2 && lower.includes(YES) && lower.includes(NO))
    return {
      type: "boolean",
      yes: options[lower.indexOf(YES)] ?? YES,
      no: options[lower.indexOf(NO)] ?? NO,
    }
  if (options.length > 1) {
    const numbers = scale(options, number)
    if (numbers) return { type: "number", ...numbers }
    const ranges = scale(options, range)
    if (ranges) return { type: "range", ...ranges }
  }
  return options.length >= SEARCH_FROM ? { type: "search" } : { type: "choice" }
}

export function toggle(values: readonly string[], option: string, multiple: boolean): string[] {
  if (values.includes(option)) return values.filter((value) => value !== option)
  return multiple ? [...values, option] : [option]
}
