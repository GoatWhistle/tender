import type { CSSProperties } from "react";
import styles from "./progress.module.css";

export interface ProgressProps {
  readonly value: number;
  readonly max: number;
  readonly label: string;
  readonly caption?: string;
}

export function Progress({ value, max, label, caption }: ProgressProps) {
  const ratio = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  return (
    <div className={styles.progress}>
      <div
        className={styles.track}
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
      >
        <span className={styles.fill} style={{ "--ratio": ratio } as CSSProperties} />
      </div>
      {caption && <p className={styles.caption}>{caption}</p>}
    </div>
  );
}
