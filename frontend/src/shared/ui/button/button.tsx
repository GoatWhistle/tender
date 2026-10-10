import type { ButtonHTMLAttributes, ReactNode } from "react";
import { clsx } from "../../class-names/clsx";
import { useLoadingIndicator } from "../../motion/use-loading-indicator";
import { Icon, type IconName } from "../icon/icon";
import { Spinner } from "../spinner/spinner";
import styles from "./button.module.css";

type Variant = "primary" | "secondary" | "ghost" | "round";
type Size = "md" | "sm";

const VARIANT: Record<Variant, string | undefined> = {
  primary: styles.primary,
  secondary: styles.secondary,
  ghost: styles.ghost,
  round: styles.round,
};

const SIZE: Record<Size, string | undefined> = {
  md: undefined,
  sm: styles.sm,
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: Variant;
  readonly size?: Size;
  readonly icon?: IconName;
  readonly iconEnd?: IconName;
  readonly pending?: boolean;
  readonly children?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  iconEnd,
  pending = false,
  disabled,
  className,
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  const showPending = useLoadingIndicator(pending, "--delay-skeleton");
  return (
    <button
      {...rest}
      type={type}
      disabled={disabled}
      aria-busy={pending || undefined}
      data-pending={showPending || undefined}
      className={clsx(styles.button, VARIANT[variant], SIZE[size], className)}
    >
      <span className={styles.content}>
        {icon && <Icon name={icon} size={variant === "round" ? 16 : 20} />}
        {children}
        {iconEnd && <Icon name={iconEnd} size={12} />}
      </span>
      {showPending && (
        <span className={styles.pending}>
          <Spinner size={20} />
        </span>
      )}
    </button>
  );
}
