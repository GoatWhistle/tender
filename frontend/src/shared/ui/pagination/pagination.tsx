import { clsx } from "../../class-names/clsx";
import styles from "./pagination.module.css";

export interface PaginationProps {
  readonly page: number;
  readonly pages: number;
  readonly label: string;
  readonly pageLabel: (n: number) => string;
  readonly onChange: (page: number) => void;
}

function window_(page: number, pages: number): (number | null)[] {
  const keep = new Set([1, pages, page - 1, page, page + 1].filter((n) => n >= 1 && n <= pages));
  const sorted = [...keep].sort((a, b) => a - b);
  return sorted.flatMap((n, i) => (i > 0 && n - (sorted[i - 1] ?? n) > 1 ? [null, n] : [n]));
}

export function Pagination({ page, pages, label, pageLabel, onChange }: PaginationProps) {
  if (pages < 2) return null;
  return (
    <nav className={styles.pagination} aria-label={label}>
      {window_(page, pages).map((n, i) =>
        n === null ? (
          <span key={`gap-${i}`} className={styles.gap} aria-hidden="true">
            …
          </span>
        ) : (
          <button
            key={n}
            type="button"
            className={clsx(styles.page, n === page && styles.current)}
            aria-current={n === page ? "page" : undefined}
            aria-label={pageLabel(n)}
            onClick={() => onChange(n)}
          >
            {n}
          </button>
        ),
      )}
    </nav>
  );
}
