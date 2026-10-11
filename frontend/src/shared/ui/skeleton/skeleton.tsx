import type { CSSProperties } from "react";
import { useLoadingIndicator } from "../../motion/use-loading-indicator";
import styles from "./skeleton.module.css";

export interface SkeletonRowsProps {
  readonly rows?: number;
  readonly label: string;
}

export function SkeletonRows({ rows = 5, label }: SkeletonRowsProps) {
  const visible = useLoadingIndicator(true, "--delay-skeleton");
  return (
    <div className={styles.rows} role="status" aria-label={label}>
      {visible &&
        Array.from({ length: rows }, (_, i) => (
          <span key={i} className={styles.row} style={{ "--i": i } as CSSProperties} />
        ))}
    </div>
  );
}
