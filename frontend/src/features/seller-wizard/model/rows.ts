import {
  isDiagnostic,
  type Diagnostic,
  type EnumProposal,
  type Fact,
  type Question,
  type SessionState,
} from "../../../api/types";
import {
  unitOf,
  type PositionCharacteristic,
  type PositionDetail,
} from "../../../entities/position";

export type RowStatus =
  | "error"
  | "question"
  | "proposal"
  | "ambiguous"
  | "missing"
  | "filled"
  | "confirmed"
  | "catalog"
  | "empty";

export interface IndexedDiagnostic {
  readonly diagnostic: Diagnostic;
  readonly index: number;
}

export interface CharacteristicRow {
  readonly key: string;
  readonly name: string;
  readonly required: boolean;
  readonly characteristic: PositionCharacteristic | null;
  readonly facts: readonly Fact[];
  readonly unit: string | null;
  readonly status: RowStatus;
  readonly diagnostics: readonly IndexedDiagnostic[];
  readonly question: Question | null;
  readonly proposal: EnumProposal | null;
  readonly unbound: boolean;
}

const norm = (s: string | null | undefined) => (s ?? "").trim().toLowerCase().replace(/ё/g, "е");

export const isActive = (f: Fact) => f.status !== "superseded" && f.status !== "deleted";

export function factText(f: Fact): string {
  if (f.origin === "decision" || f.kind === "interval") return String(f.value);
  if (f.kind === "range" && Array.isArray(f.value)) return `${f.value[0]}–${f.value[1]}`;
  return f.raw_value;
}

export function diagnosticsOf(state: SessionState): IndexedDiagnostic[] {
  return [...state.errors.filter(isDiagnostic), ...(state.normalizations ?? [])].map(
    (diagnostic, index) => ({ diagnostic, index }),
  );
}

function statusOf(
  facts: readonly Fact[],
  required: boolean,
  diagnostics: readonly IndexedDiagnostic[],
  question: Question | null,
  proposal: EnumProposal | null,
): RowStatus {
  if (diagnostics.some((d) => d.diagnostic.kind !== "synonym")) return "error";
  if (proposal) return "proposal";
  if (question) return "question";
  if (facts.some((f) => f.status === "ambiguous")) return "ambiguous";
  if (facts.length === 0) return required ? "missing" : "empty";
  if (facts.every((f) => f.origin === "catalog")) return "catalog";
  if (facts.every((f) => f.status === "confirmed_by_user" || f.origin === "user"))
    return "confirmed";
  return "filled";
}

const ORDER: Record<RowStatus, number> = {
  error: 0,
  proposal: 1,
  question: 2,
  ambiguous: 3,
  missing: 4,
  filled: 5,
  confirmed: 5,
  catalog: 5,
  empty: 6,
};

export function buildRows(
  state: SessionState,
  position: PositionDetail | null,
): CharacteristicRow[] {
  const facts = state.facts.filter(isActive);
  const diagnostics = diagnosticsOf(state);
  const proposals = state.enum_proposals ?? [];
  const missing = new Set(state.missing_required.map((m) => norm(m.name)));
  const used = new Set<string>();
  const factName = (f: Fact) => norm(f.characteristic_name);

  const forName = (name: string, characteristic: PositionCharacteristic | null) => {
    const key = norm(name);
    const own = facts.filter((f) => factName(f) === key);
    own.forEach((f) => used.add(f.id));
    const ids = new Set(own.map((f) => f.id));
    const diags = diagnostics.filter(
      ({ diagnostic: d }) =>
        (d.fact_id && ids.has(d.fact_id)) ||
        (!d.fact_id && d.rule_ref.some((r) => norm(r.characteristic_name) === key)),
    );
    const question =
      state.next_question && norm(state.next_question.characteristic) === key
        ? state.next_question
        : null;
    const proposal = proposals.find((p) => norm(p.characteristic) === key) ?? null;
    const required = characteristic?.required ?? missing.has(key);
    return {
      key: characteristic?.code ?? `fact:${key}`,
      name,
      required,
      characteristic,
      facts: own,
      unit:
        own.find((f) => f.raw_unit)?.raw_unit ?? (characteristic ? unitOf(characteristic) : null),
      status: statusOf(own, required, diags, question, proposal),
      diagnostics: diags,
      question,
      proposal,
      unbound: false,
    } satisfies CharacteristicRow;
  };

  const rows = (position?.characteristics ?? []).map((c) => forName(c.name, c));
  const extra = facts
    .filter((f) => !used.has(f.id) && f.characteristic_name)
    .map((f) => f.characteristic_name as string)
    .filter((name, i, all) => all.indexOf(name) === i)
    .map((name) => forName(name, null));
  const unbound = facts
    .filter((f) => !f.characteristic_name)
    .map((f): CharacteristicRow => ({
      key: `unbound:${f.id}`,
      name: f.source?.quote ?? f.raw_value,
      required: false,
      characteristic: null,
      facts: [f],
      unit: f.raw_unit,
      status: "ambiguous",
      diagnostics: diagnostics.filter((d) => d.diagnostic.fact_id === f.id),
      question: null,
      proposal: null,
      unbound: true,
    }));
  return [...unbound, ...rows, ...extra].sort(
    (a, b) => ORDER[a.status] - ORDER[b.status] || Number(b.required) - Number(a.required),
  );
}

export function unboundDiagnostics(state: SessionState, rows: readonly CharacteristicRow[]) {
  const bound = new Set(rows.flatMap((r) => r.diagnostics.map((d) => d.index)));
  return diagnosticsOf(state).filter((d) => !bound.has(d.index) && d.diagnostic.kind !== "synonym");
}

export function completeness(rows: readonly CharacteristicRow[]) {
  const required = rows.filter((r) => r.required);
  const done = required.filter((r) => ["filled", "confirmed", "catalog"].includes(r.status));
  return { done: done.length, total: required.length };
}
