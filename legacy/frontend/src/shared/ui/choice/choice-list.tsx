import { useId } from "react";
import { clsx } from "../../class-names/clsx";
import styles from "./choice-list.module.css";

export interface ChoiceOption {
  readonly id: string;
  readonly label: string;
  readonly hint?: string;
}

export interface ChoiceListProps {
  readonly legend: string;
  readonly options: readonly ChoiceOption[];
  readonly value: readonly string[];
  readonly multiple?: boolean;
  readonly disabled?: boolean;
  readonly compact?: boolean;
  readonly onChange: (value: string[]) => void;
}

export function ChoiceList({
  legend,
  options,
  value,
  multiple = false,
  disabled = false,
  compact = false,
  onChange,
}: ChoiceListProps) {
  const name = useId();
  const toggle = (id: string) => {
    if (!multiple) return onChange([id]);
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  };
  return (
    <fieldset className={clsx(styles.list, compact && styles.compact)} disabled={disabled}>
      <legend className="sr-only">{legend}</legend>
      {options.map((o) => {
        const checked = value.includes(o.id);
        return (
          <label key={o.id} className={clsx(styles.option, checked && styles.checked)}>
            <input
              className={styles.input}
              type={multiple ? "checkbox" : "radio"}
              name={name}
              checked={checked}
              onChange={() => toggle(o.id)}
            />
            <span
              className={clsx(styles.mark, multiple ? styles.box : styles.dot)}
              aria-hidden="true"
            />
            <span className={styles.text}>
              <span>{o.label}</span>
              {o.hint && !compact && <span className={styles.hint}>{o.hint}</span>}
            </span>
            {o.hint && compact && <span className={styles.count}>{o.hint}</span>}
          </label>
        );
      })}
    </fieldset>
  );
}
