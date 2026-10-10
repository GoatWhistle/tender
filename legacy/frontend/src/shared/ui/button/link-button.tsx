import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { clsx } from "../../class-names/clsx";
import { Icon, type IconName } from "../icon/icon";
import styles from "./button.module.css";

export interface LinkButtonProps {
  readonly to: string;
  readonly variant?: "primary" | "secondary" | "ghost";
  readonly icon?: IconName;
  readonly children: ReactNode;
}

const VARIANT = {
  primary: styles.primary,
  secondary: styles.secondary,
  ghost: styles.ghost,
} as const;

export function LinkButton({ to, variant = "secondary", icon, children }: LinkButtonProps) {
  return (
    <Link to={to} className={clsx(styles.button, VARIANT[variant])}>
      <span className={styles.content}>
        {icon && <Icon name={icon} size={20} />}
        {children}
      </span>
    </Link>
  );
}
