import type { ReactNode } from "react";
import { t } from "../../../shared/i18n";
import { useLoadingIndicator } from "../../../shared/motion";
import { Spinner } from "../../../shared/ui/spinner/spinner";
import styles from "./step-layout.module.css";

export interface StepLayoutProps {
  readonly id: string;
  readonly heading: string;
  readonly lead?: ReactNode;
  readonly aside?: ReactNode;
  readonly children: ReactNode;
  readonly back?: ReactNode;
  readonly next?: ReactNode;
  readonly busy?: boolean;
}

export function StepLayout({
  id,
  heading,
  lead,
  aside,
  children,
  back,
  next,
  busy,
}: StepLayoutProps) {
  const loading = useLoadingIndicator(Boolean(busy));
  return (
    <>
      <div className={styles.body}>
        <header className={styles.head}>
          <div className={styles.intro}>
            <h2 id={`step-${id}`} className={styles.heading}>
              {heading}
            </h2>
            {lead && <div className={styles.lead}>{lead}</div>}
          </div>
          {aside && <div className={styles.aside}>{aside}</div>}
        </header>
        {children}
      </div>
      {(back || next || loading) && (
        <footer className={styles.footer}>
          <div className={styles.back}>{back}</div>
          <div className={styles.next}>
            {loading && (
              <span className={styles.busy} role="status">
                <Spinner size={16} />
                {t("seller:busy")}
              </span>
            )}
            {next}
          </div>
        </footer>
      )}
    </>
  );
}
