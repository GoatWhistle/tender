import type { Session } from "../rag";
import { buildRows } from "./rows";

export interface Summary {
  readonly groups: number;
  readonly questions: number;
  readonly automatic: number;
  readonly total: number;
  readonly fixes: number;
}

export function summarize(session: Session): Summary {
  const rows = buildRows(session).filter((r) => r.status !== "empty");
  const automatic = rows.filter((r) => r.status !== "missing" && r.origin !== "manual").length;
  return {
    groups: session.groups.length,
    questions: Object.keys(session.answers).length,
    automatic,
    total: rows.length,
    fixes: session.fixes.length,
  };
}
