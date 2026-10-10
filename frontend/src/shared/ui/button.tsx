import clsx from "clsx"
import type { ButtonHTMLAttributes } from "react"
import styles from "./button.module.css"
import { Icon, type IconName } from "./icon"

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: "primary" | "secondary" | "ghost" | "row"
  readonly icon?: IconName
  readonly pending?: boolean
}
export function Button({
  variant = "secondary",
  icon,
  pending = false,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      type={props.type ?? "button"}
      className={clsx(styles.button, styles[variant], className)}
      disabled={disabled || pending}
      aria-busy={pending}
      data-state={pending ? "pending" : "idle"}
    >
      {icon && <Icon name={icon} />}
      {children}
    </button>
  )
}
