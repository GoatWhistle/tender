import type { ReactNode } from "react";
import { clsx } from "../../class-names/clsx";
import { Icon, type IconName } from "../icon/icon";
import styles from "./banner.module.css";

type Tone = "info" | "error" | "warning" | "success";

const TONE: Record<Tone, string | undefined> = {
  info: styles.info,
  error: styles.error,
  warning: styles.warning,
  success: styles.success,
};

const ICON: Record<Tone, IconName> = {
  info: "note",
  error: "attention",
  warning: "attention",
  success: "done",
};

export interface BannerProps {
  readonly tone?: Tone;
  readonly title: string;
  readonly children?: ReactNode;
  readonly actions?: ReactNode;
  readonly live?: boolean;
}

export function Banner({ tone = "info", title, children, actions, live = false }: BannerProps) {
  return (
    <section
      className={clsx(styles.banner, TONE[tone])}
      role={tone === "error" ? "alert" : live ? "status" : undefined}
    >
      <Icon name={ICON[tone]} size={24} />
      <div className={styles.body}>
        <p className={styles.title}>{title}</p>
        {children && <div className={styles.text}>{children}</div>}
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </section>
  );
}
