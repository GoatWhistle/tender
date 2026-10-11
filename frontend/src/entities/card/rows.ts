import type { Band, Characteristic, Doubt, FixedValue, Origin, Session } from "../rag";

const list = (value: FixedValue): readonly string[] =>
  Array.isArray(value) ? value : [String(value)];

export type RowStatus = "missing" | "doubt" | "filled" | "fixed" | "empty";

export interface Row {
  readonly key: string;
  readonly name: string;
  readonly required: boolean;
  readonly multiple: boolean;
  readonly options: readonly string[];
  readonly values: readonly string[];
  readonly unit: string | null;
  readonly bands: readonly Band[];
  readonly number: number | null;
  readonly origin: Origin | null;
  readonly warning: Doubt | null;
  readonly fixed: boolean;
  readonly status: RowStatus;
}

const ORDER: Record<RowStatus, number> = { missing: 0, doubt: 1, filled: 2, fixed: 3, empty: 4 };

function statusOf(c: Characteristic): RowStatus {
  if (c.warning) return "doubt";
  if (c.values.length > 0 || typeof c.number === "number") return "filled";
  return c.required ? "missing" : "empty";
}

export function buildRows(session: Session): Row[] {
  const editable: Row[] = session.characteristics.map((c) => ({
    key: `c:${c.name}`,
    name: c.name,
    required: c.required,
    multiple: c.multiple,
    options: c.options,
    values: c.values,
    unit: c.unit ?? null,
    bands: c.bands ?? [],
    number: typeof c.number === "number" ? c.number : null,
    origin: c.origin ?? null,
    warning: c.warning ?? null,
    fixed: false,
    status: statusOf(c),
  }));
  const fixed: Row[] = Object.entries(session.position?.fixed ?? {}).map(([name, value]) => {
    const values = list(value);
    return {
      key: `f:${name}`,
      name,
      required: true,
      multiple: values.length > 1,
      options: values,
      values,
      unit: null,
      bands: [],
      number: null,
      origin: null,
      warning: null,
      fixed: true,
      status: "fixed" as const,
    };
  });
  return [...editable, ...fixed].sort(
    (a, b) => ORDER[a.status] - ORDER[b.status] || Number(b.required) - Number(a.required),
  );
}

export function valueText(row: Row, format: (n: number) => string): string {
  if (row.number !== null) return format(row.number);
  return row.values.join("; ");
}

export function completeness(rows: readonly Row[]) {
  const required = rows.filter((r) => r.required && !r.fixed);
  const done = required.filter((r) => r.status === "filled" || r.status === "doubt").length;
  return { done, total: required.length };
}

export const needsAction = (r: Row) => r.status === "missing" || r.status === "doubt";
