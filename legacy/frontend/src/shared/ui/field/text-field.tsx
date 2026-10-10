import type { InputHTMLAttributes } from "react";
import { clsx } from "../../class-names/clsx";
import styles from "./field.module.css";

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  readonly label: string;
  readonly hideLabel?: boolean;
}

export function TextField({ label, hideLabel = false, id, className, ...rest }: TextFieldProps) {
  return (
    <div className={clsx(styles.field, className)}>
      <label htmlFor={id} className={hideLabel ? "sr-only" : styles.label}>
        {label}
      </label>
      <input {...rest} id={id} className={styles.control} />
    </div>
  );
}
