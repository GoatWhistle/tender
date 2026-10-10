import { useId, useState, type ReactNode } from "react";
import { clsx } from "../../class-names/clsx";
import { Collapse } from "../../motion/collapse";
import { Icon } from "../icon/icon";
import styles from "./disclosure.module.css";

export interface DisclosureProps {
  readonly summary: ReactNode;
  readonly children: ReactNode;
  readonly defaultOpen?: boolean;
}

export function Disclosure({ summary, children, defaultOpen = false }: DisclosureProps) {
  const [open, setOpen] = useState(defaultOpen);
  const panel = useId();
  return (
    <div
      className={clsx(styles.disclosure, open && styles.open)}
      data-state={open ? "open" : "closed"}
    >
      <button
        type="button"
        className={styles.trigger}
        aria-expanded={open}
        aria-controls={panel}
        onClick={() => setOpen(!open)}
      >
        <Icon name="chevron-right-small" size={12} className={styles.chevron} />
        {summary}
      </button>
      <Collapse id={panel} open={open} className={styles.panel}>
        {children}
      </Collapse>
    </div>
  );
}
