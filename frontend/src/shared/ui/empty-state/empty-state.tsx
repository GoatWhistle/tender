import type { ReactNode } from "react";
import { Illustration, type IllustrationName } from "../illustration/illustration";
import styles from "./empty-state.module.css";

export interface EmptyStateProps {
  readonly illustration: IllustrationName;
  readonly title: string;
  readonly children?: ReactNode;
  readonly actions?: ReactNode;
  readonly heading?: "h1" | "h2";
}

export function EmptyState({
  illustration,
  title,
  children,
  actions,
  heading: Heading = "h2",
}: EmptyStateProps) {
  return (
    <section className={styles.empty}>
      <Illustration name={illustration} size="lg" />
      <Heading className={styles.title}>{title}</Heading>
      {children && <div className={styles.text}>{children}</div>}
      {actions && <div className={styles.actions}>{actions}</div>}
    </section>
  );
}
