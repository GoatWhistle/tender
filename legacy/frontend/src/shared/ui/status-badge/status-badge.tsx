import { clsx } from "../../class-names/clsx";
import styles from "./status-badge.module.css";

export type BadgeTone = "neutral" | "info" | "success" | "warning" | "error";

const TONE: Record<BadgeTone, string | undefined> = {
  neutral: styles.neutral,
  info: styles.info,
  success: styles.success,
  warning: styles.warning,
  error: styles.error,
};

export interface StatusBadgeProps {
  readonly tone: BadgeTone;
  readonly label: string;
}

export function StatusBadge({ tone, label }: StatusBadgeProps) {
  return (
    <span className={clsx(styles.badge, TONE[tone])}>
      <span className={styles.dot} aria-hidden="true" />
      {label}
    </span>
  );
}
