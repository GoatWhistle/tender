import { getLocale } from "../../shared/i18n";
import type { Session } from "../rag";
import { buildRows, valueText } from "./rows";

export type CardSource = "fixed" | "filled" | "extra" | "missing";

export interface CardRow {
  readonly key: string;
  readonly name: string;
  readonly value: string;
  readonly unit: string;
  readonly source: CardSource;
}

export function cardRows(session: Session): CardRow[] {
  const format = (n: number) => new Intl.NumberFormat(getLocale()).format(n);
  const rows: CardRow[] = buildRows(session)
    .filter((r) => r.status !== "empty")
    .map((r) => ({
      key: r.key,
      name: r.name,
      value: valueText(r, format),
      unit: r.unit ?? "",
      source: r.fixed ? "fixed" : r.status === "missing" ? "missing" : "filled",
    }));
  const extras: CardRow[] = session.extras.map((e, i) => ({
    key: `e:${i}`,
    name: e.name,
    value: e.value,
    unit: "",
    source: "extra",
  }));
  return [...rows, ...extras];
}

export function exportCard(session: Session): void {
  const position = session.position;
  if (!position) return;
  const card = {
    code: position.code,
    name: position.name,
    okpd2: position.okpd2,
    okpd2_name: position.okpd2_name,
    description: session.description,
    characteristics: cardRows(session).map(({ name, value, unit, source }) => ({
      name,
      value,
      unit,
      source,
    })),
  };
  const blob = new Blob([`${JSON.stringify(card, null, 2)}\n`], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `ste-${position.code}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url));
}
