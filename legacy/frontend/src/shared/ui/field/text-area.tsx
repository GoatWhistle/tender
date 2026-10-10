import { forwardRef, type TextareaHTMLAttributes } from "react";
import { clsx } from "../../class-names/clsx";
import styles from "./field.module.css";

export interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  readonly label: string;
  readonly hint?: string;
  readonly invalid?: boolean;
  readonly size?: "md" | "lg";
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(function TextArea(
  { label, hint, invalid = false, size = "md", id, className, ...rest },
  ref,
) {
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className={clsx(styles.field, className)}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <textarea
        {...rest}
        ref={ref}
        id={id}
        aria-invalid={invalid || undefined}
        aria-describedby={hintId}
        className={clsx(styles.control, styles.area, size === "lg" && styles.large)}
      />
      {hint && (
        <p id={hintId} className={clsx(styles.hint, invalid && styles.hintError)}>
          {hint}
        </p>
      )}
    </div>
  );
});
