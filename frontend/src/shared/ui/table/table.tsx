import type { CSSProperties, ReactNode } from "react";
import { clsx } from "../../class-names/clsx";
import styles from "./table.module.css";

export type CellTone = "default" | "error" | "warning" | "success" | "muted";

export interface Column<Row> {
  readonly key: string;
  readonly label: string;
  readonly width?: string;
  readonly align?: "start" | "end";
  readonly render: (row: Row) => ReactNode;
  readonly tone?: (row: Row) => CellTone;
}

export interface TableProps<Row> {
  readonly caption: string;
  readonly columns: readonly Column<Row>[];
  readonly rows: readonly Row[];
  readonly rowKey: (row: Row) => string;
  readonly rowTone?: (row: Row) => CellTone;
  readonly expanded?: (row: Row) => ReactNode;
  readonly empty?: ReactNode;
  readonly appear?: boolean;
}

const TONE: Record<CellTone, string | undefined> = {
  default: undefined,
  error: styles.error,
  warning: styles.warning,
  success: styles.success,
  muted: styles.muted,
};

export function Table<Row>({
  caption,
  columns,
  rows,
  rowKey,
  rowTone,
  expanded,
  empty,
  appear = true,
}: TableProps<Row>) {
  const template = columns.map((c) => c.width ?? "minmax(0, 1fr)").join(" ");
  return (
    <div className={styles.wrap} role="table" aria-label={caption}>
      <div className={styles.head} role="row" style={{ "--cols": template } as CSSProperties}>
        {columns.map((c) => (
          <span
            key={c.key}
            role="columnheader"
            className={clsx(styles.th, c.align === "end" && styles.end)}
          >
            {c.label}
          </span>
        ))}
      </div>
      {rows.length === 0 && empty && <div className={styles.empty}>{empty}</div>}
      {rows.map((row, index) => {
        const extra = expanded?.(row);
        return (
          <div
            key={rowKey(row)}
            role="rowgroup"
            className={clsx(
              styles.group,
              appear && styles.appear,
              TONE[rowTone?.(row) ?? "default"],
            )}
            style={{ "--i": index } as CSSProperties}
          >
            <div className={styles.row} role="row" style={{ "--cols": template } as CSSProperties}>
              {columns.map((c) => (
                <span
                  key={c.key}
                  role="cell"
                  className={clsx(
                    styles.td,
                    TONE[c.tone?.(row) ?? "default"],
                    c.align === "end" && styles.end,
                  )}
                >
                  {c.render(row)}
                </span>
              ))}
            </div>
            {extra}
          </div>
        );
      })}
    </div>
  );
}
