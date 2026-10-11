import { useEffect, useId, useRef, type ReactNode } from "react";
import { clsx } from "../../class-names/clsx";
import { t } from "../../i18n";
import { Button } from "../button/button";
import styles from "./dialog.module.css";

type Size = "md" | "sm";

const SIZE: Record<Size, string | undefined> = {
  md: undefined,
  sm: styles.sm,
};

export interface DialogProps {
  readonly open: boolean;
  readonly size?: Size;
  readonly media?: ReactNode;
  readonly title: string;
  readonly onClose: () => void;
  readonly children?: ReactNode;
  readonly actions?: ReactNode;
}

export function Dialog({
  open,
  size = "md",
  media,
  title,
  onClose,
  children,
  actions,
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const id = useId();
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (open && !node.open) {
      node.showModal();
      heading.current?.focus();
    }
    if (!open && node.open) node.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={clsx(styles.dialog, SIZE[size])}
      aria-labelledby={id}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className={styles.panel}>
        <Button
          variant="ghost"
          icon="close"
          className={styles.close}
          aria-label={t("common:actions.close")}
          onClick={onClose}
        />
        {media && <div className={styles.media}>{media}</div>}
        <h2 id={id} ref={heading} tabIndex={-1} className={styles.title}>
          {title}
        </h2>
        {children && (
          <div className={styles.body} tabIndex={0} role="region" aria-labelledby={id}>
            {children}
          </div>
        )}
        {actions && <footer className={styles.footer}>{actions}</footer>}
      </div>
    </dialog>
  );
}
