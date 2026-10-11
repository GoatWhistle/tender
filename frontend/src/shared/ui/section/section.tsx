import { useId, type ReactNode } from "react";
import styles from "./section.module.css";

export interface SectionProps {
  readonly title: string;
  readonly lead?: ReactNode;
  readonly actions?: ReactNode;
  readonly children: ReactNode;
}

export function Section({ title, lead, actions, children }: SectionProps) {
  const id = useId();
  return (
    <section className={styles.section} aria-labelledby={id}>
      <header className={styles.head}>
        <div className={styles.intro}>
          <h3 id={id} className={styles.title}>
            {title}
          </h3>
          {lead && <p className={styles.lead}>{lead}</p>}
        </div>
        {actions && <div className={styles.actions}>{actions}</div>}
      </header>
      {children}
    </section>
  );
}
