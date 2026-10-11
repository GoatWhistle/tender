import type { ReactNode } from "react";
import { clsx } from "../../class-names/clsx";
import styles from "./facts.module.css";

export interface Fact {
  readonly key: string;
  readonly label: string;
  readonly value: ReactNode;
  readonly wide?: boolean;
}

type Layout = "tiles" | "rows";

const LAYOUT: Record<Layout, string | undefined> = {
  tiles: styles.tiles,
  rows: styles.rows,
};

export interface FactsProps {
  readonly items: readonly Fact[];
  readonly layout?: Layout;
}

export function Facts({ items, layout = "tiles" }: FactsProps) {
  return (
    <dl className={clsx(styles.facts, LAYOUT[layout])}>
      {items.map((fact) => (
        <div key={fact.key} className={clsx(styles.item, fact.wide && styles.wide)}>
          <dt className={styles.label}>{fact.label}</dt>
          <dd className={styles.value}>{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}
