import type { ReactNode } from "react";
import type { Diagnostic } from "../../../api/types";
import styles from "./marked-text.module.css";

export interface MarkedTextProps {
  readonly text: string;
  readonly marks: readonly Diagnostic[];
}

export function MarkedText({ text, marks }: MarkedTextProps) {
  const chars = Array.from(text);
  const spans = marks
    .filter(
      (d) =>
        d.source.start >= 0 &&
        d.source.end <= chars.length &&
        chars.slice(d.source.start, d.source.end).join("") === d.source_quote,
    )
    .sort((a, b) => a.source.start - b.source.start);
  const nodes: ReactNode[] = [];
  let cursor = 0;
  for (const d of spans) {
    if (d.source.start < cursor) continue;
    nodes.push(chars.slice(cursor, d.source.start).join(""));
    nodes.push(
      <mark
        key={`${d.source.start}:${d.source.end}`}
        className={d.kind === "synonym" ? styles.synonym : styles.error}
        title={d.explanation}
      >
        {chars.slice(d.source.start, d.source.end).join("")}
      </mark>,
    );
    cursor = d.source.end;
  }
  nodes.push(chars.slice(cursor).join(""));
  return <>{nodes}</>;
}
