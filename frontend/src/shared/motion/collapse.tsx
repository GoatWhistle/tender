import type { ReactNode } from "react";
import { clsx } from "../class-names/clsx";
import { useLatched } from "./use-latched";
import { usePresence } from "./use-presence";
import styles from "./collapse.module.css";

export interface CollapseProps {
  readonly open: boolean;
  readonly children: ReactNode;
  readonly id?: string;
  readonly className?: string;
  readonly role?: "row" | "region";
}

export function Collapse({ open, children, id, className, role }: CollapseProps) {
  const state = usePresence(open);
  const content = useLatched(open ? children : null, state === "closing");
  if (state === "closed") return null;
  return (
    <div id={id} role={role} className={clsx(styles.collapse, className)} data-state={state}>
      {content}
    </div>
  );
}
