import type { CSSProperties } from "react";
import { clsx } from "../../class-names/clsx";
import styles from "./stepper.module.css";

export interface StepItem {
  readonly id: string;
  readonly label: string;
}

export interface StepperProps {
  readonly steps: readonly StepItem[];
  readonly current: number;
  readonly reachable: number;
  readonly label: string;
  readonly onSelect: (index: number) => void;
}

type State = "done" | "current" | "todo";

const STATE: Record<State, string | undefined> = {
  done: styles.done,
  current: styles.current,
  todo: styles.todo,
};

export function Stepper({ steps, current, reachable, label, onSelect }: StepperProps) {
  return (
    <nav aria-label={label}>
      <ol className={styles.stepper} style={{ "--steps": steps.length } as CSSProperties}>
        {steps.map((step, index) => {
          const state: State = index < current ? "done" : index === current ? "current" : "todo";
          const enabled = index <= reachable && index !== current;
          return (
            <li key={step.id} className={clsx(styles.step, STATE[state])} data-state={state}>
              <button
                type="button"
                className={styles.target}
                disabled={!enabled}
                aria-current={state === "current" ? "step" : undefined}
                onClick={() => onSelect(index)}
              >
                <span className={styles.circle}>{index + 1}</span>
                <span className={styles.label}>{step.label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
