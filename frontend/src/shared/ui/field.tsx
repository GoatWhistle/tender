import type { InputHTMLAttributes, ReactNode } from "react"
import styles from "./field.module.css"
import { Icon } from "./icon"

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  readonly label: string
  readonly suffix?: string | undefined
  readonly issue?: boolean
  readonly children?: ReactNode
}
export function Field({
  label,
  suffix,
  issue = false,
  children,
  id,
  required,
  ...props
}: FieldProps) {
  return (
    <div className={styles.field} data-invalid={issue}>
      <label htmlFor={id}>
        {label}
        {required && (
          <span className={styles.required} aria-hidden="true">
            *
          </span>
        )}
      </label>
      <div className={styles.inputWrap}>
        <input
          {...props}
          data-focus="container"
          id={id}
          required={required}
          aria-invalid={issue}
          aria-describedby={
            [suffix ? `${id}-unit` : "", children ? `${id}-help` : ""].filter(Boolean).join(" ") ||
            undefined
          }
        />
        {suffix && (
          <span id={`${id}-unit`} className={styles.suffix}>
            {suffix}
          </span>
        )}
        {issue && (
          <span className={styles.alert}>
            <Icon name="alert" size={16} />
          </span>
        )}
      </div>
      {children && (
        <div id={`${id}-help`} className={styles.help}>
          {children}
        </div>
      )}
    </div>
  )
}
