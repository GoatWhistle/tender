import clsx from "clsx"
import boxes from "./assets/boxes.svg"
import funnel from "./assets/funnel.svg"
import laptop from "./assets/laptop.svg"
import magnifier from "./assets/magnifier.svg"
import robot from "./assets/robot.svg"
import target from "./assets/target.svg"
import styles from "./illustration.module.css"

const source = { boxes, funnel, laptop, magnifier, robot, target } as const

export type IllustrationName = keyof typeof source

export function Illustration({
  name,
  size = "md",
  className,
}: {
  readonly name: IllustrationName
  readonly size?: "sm" | "md" | "lg"
  readonly className?: string
}) {
  return (
    <img
      src={source[name]}
      alt=""
      aria-hidden="true"
      draggable={false}
      className={clsx(styles.illustration, styles[size], className)}
    />
  )
}
