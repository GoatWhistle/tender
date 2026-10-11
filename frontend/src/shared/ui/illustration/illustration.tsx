import { clsx } from "../../class-names/clsx";
import boxes from "./assets/boxes.svg";
import envelope from "./assets/envelope.svg";
import funnel from "./assets/funnel.svg";
import laptop from "./assets/laptop.svg";
import magnifier from "./assets/magnifier.svg";
import robot from "./assets/robot.svg";
import target from "./assets/target.svg";
import styles from "./illustration.module.css";

const SOURCE = { boxes, envelope, funnel, laptop, magnifier, robot, target } as const;

export type IllustrationName = keyof typeof SOURCE;

type Size = "sm" | "md" | "lg";

const SIZE: Record<Size, string | undefined> = {
  sm: styles.sm,
  md: styles.md,
  lg: styles.lg,
};

export interface IllustrationProps {
  readonly name: IllustrationName;
  readonly size?: Size;
  readonly className?: string;
}

export function Illustration({ name, size = "md", className }: IllustrationProps) {
  return (
    <img
      src={SOURCE[name]}
      alt=""
      aria-hidden="true"
      draggable={false}
      className={clsx(styles.illustration, SIZE[size], className)}
    />
  );
}
