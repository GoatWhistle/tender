import styles from "./spinner.module.css";

export interface SpinnerProps {
  readonly size?: 16 | 20 | 24 | 32;
  readonly label?: string;
}

export function Spinner({ size = 20, label }: SpinnerProps) {
  return (
    <span
      className={styles.spinner}
      style={{ inlineSize: size, blockSize: size }}
      role={label ? "status" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    />
  );
}
