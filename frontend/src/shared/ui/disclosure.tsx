import { type ReactNode, useId } from "react"
import { useDisclosureMotion } from "@/shared/motion/use-disclosure-motion"
import { Button } from "./button"
import styles from "./disclosure.module.css"
import { Icon } from "./icon"
export function Disclosure({
  title,
  status,
  children,
  initialOpen = false,
}: {
  readonly title: string
  readonly status: ReactNode
  readonly children: ReactNode
  readonly initialOpen?: boolean
}) {
  const id = useId()
  const { ref, open, present, toggle } = useDisclosureMotion(initialOpen)
  return (
    <section className={styles.group} data-state={open ? "open" : "closed"}>
      <Button
        className={styles.trigger}
        variant="ghost"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={id}
      >
        <strong>{title}</strong>
        <span className={styles.status}>{status}</span>
        <span className={styles.chevron}>
          <Icon name="expand" />
        </span>
      </Button>
      {present && (
        <div ref={ref} id={id} className={styles.panel}>
          {children}
        </div>
      )}
    </section>
  )
}
