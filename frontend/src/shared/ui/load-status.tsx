import type { ReactNode } from "react"
import styles from "./load-status.module.css"

export function LoadStatus({
  alert = false,
  children,
}: {
  readonly alert?: boolean
  readonly children: ReactNode
}) {
  return (
    <div className={styles.status} role={alert ? "alert" : "status"}>
      {children}
    </div>
  )
}
