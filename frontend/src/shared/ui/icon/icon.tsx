import type { CSSProperties } from "react";
import { clsx } from "../../class-names/clsx";
import attention from "./assets/attention.svg";
import check from "./assets/check.svg";
import chevronLeft from "./assets/chevron-left.svg";
import chevronRightSmall from "./assets/chevron-right-small.svg";
import close from "./assets/close.svg";
import done from "./assets/done.svg";
import edit from "./assets/edit.svg";
import history from "./assets/history.svg";
import monitor from "./assets/monitor.svg";
import moon from "./assets/moon.svg";
import note from "./assets/note.svg";
import plus from "./assets/plus.svg";
import products from "./assets/products.svg";
import question from "./assets/question.svg";
import quit from "./assets/quit.svg";
import search from "./assets/search.svg";
import sun from "./assets/sun.svg";
import trash from "./assets/trash.svg";
import styles from "./icon.module.css";

const MONO = {
  check,
  "chevron-left": chevronLeft,
  "chevron-right": chevronLeft,
  "chevron-right-small": chevronRightSmall,
  close,
  edit,
  history,
  monitor,
  moon,
  note,
  plus,
  products,
  question,
  quit,
  search,
  sun,
  trash,
} as const;

const COLOR = { attention, done } as const;

export type IconName = keyof typeof MONO | keyof typeof COLOR;

type Size = 12 | 16 | 20 | 24 | 30 | 48;

export interface IconProps {
  readonly name: IconName;
  readonly size?: Size;
  readonly label?: string;
  readonly className?: string;
}

export function Icon({ name, size = 20, label, className }: IconProps) {
  const a11y = label ? { role: "img", "aria-label": label } : { "aria-hidden": true };
  if (name in COLOR) {
    return (
      <img
        src={COLOR[name as keyof typeof COLOR]}
        width={size}
        height={size}
        alt={label ?? ""}
        className={clsx(styles.icon, className)}
        aria-hidden={label ? undefined : true}
      />
    );
  }
  const src = MONO[name as keyof typeof MONO];
  return (
    <span
      {...a11y}
      className={clsx(styles.icon, styles.mono, name === "chevron-right" && styles.flip, className)}
      style={{ "--icon-src": `url("${src}")`, "--icon-size": `${size}px` } as CSSProperties}
    />
  );
}
