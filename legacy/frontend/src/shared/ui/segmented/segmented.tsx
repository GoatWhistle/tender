import { useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { clsx } from "../../class-names/clsx";
import { Icon, type IconName } from "../icon/icon";
import styles from "./segmented.module.css";

export interface SegmentedOption<V extends string> {
  readonly value: V;
  readonly label: string;
  readonly icon?: IconName;
  readonly short?: string;
}

export interface SegmentedProps<V extends string> {
  readonly label: string;
  readonly options: readonly SegmentedOption<V>[];
  readonly value: V;
  readonly onChange: (value: V) => void;
  readonly display?: "label" | "icon" | "short";
}

export function Segmented<V extends string>({
  label,
  options,
  value,
  onChange,
  display = "label",
}: SegmentedProps<V>) {
  const refs = useRef(new Map<V, HTMLButtonElement>());
  const [box, setBox] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  useLayoutEffect(() => {
    const el = refs.current.get(value);
    if (!el) return;
    const next = { x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight };
    setBox((b) =>
      b && b.x === next.x && b.y === next.y && b.w === next.w && b.h === next.h ? b : next,
    );
  }, [value, options.length]);

  return (
    <div
      className={clsx(styles.segmented, display !== "label" && styles.compact)}
      role="radiogroup"
      aria-label={label}
    >
      {box && (
        <span
          className={styles.indicator}
          aria-hidden="true"
          style={
            {
              "--x": `${box.x}px`,
              "--y": `${box.y}px`,
              "--w": `${box.w}px`,
              "--h": `${box.h}px`,
            } as CSSProperties
          }
        />
      )}
      {options.map((o) => (
        <button
          key={o.value}
          ref={(el) => {
            if (el) refs.current.set(o.value, el);
          }}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          aria-label={display === "label" ? undefined : o.label}
          title={display === "label" ? undefined : o.label}
          className={styles.option}
          onClick={() => onChange(o.value)}
        >
          {display === "icon" && o.icon ? (
            <Icon name={o.icon} size={16} />
          ) : display === "short" ? (
            (o.short ?? o.label)
          ) : (
            o.label
          )}
        </button>
      ))}
    </div>
  );
}
