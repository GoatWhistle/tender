import type { SessionState } from "../../../api/types";

export const STEPS = ["describe", "position", "characteristics", "card"] as const;

export type StepId = (typeof STEPS)[number];

export function stepIndex(id: string | null): number {
  const index = STEPS.indexOf(id as StepId);
  return index < 0 ? 0 : index;
}

export function reachableStep(state: SessionState | null): number {
  if (!state?.path || state.status === "technical_error") return 0;
  if (state.status === "resolved") return 3;
  return 2;
}

export function compatibleCandidates(state: SessionState) {
  return state.candidates.filter((c) => !c.excluded);
}

export function chosenPositionCode(state: SessionState | null): string | null {
  if (!state?.path) return null;
  const compatible = compatibleCandidates(state);
  if (compatible.length === 1 && compatible[0]) return compatible[0].code;
  return state.path.group.code;
}

export function isNarrowingQuestion(state: SessionState): boolean {
  const kind = state.next_question?.kind;
  return kind === "discriminate" || kind === "conflict" || kind === "purpose";
}
