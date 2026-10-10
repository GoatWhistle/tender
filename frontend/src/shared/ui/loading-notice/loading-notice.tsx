import { Spinner } from "@/shared/motion/primitives"
import { useLoadingIndicator } from "@/shared/motion/use-loading-indicator"
import styles from "./loading-notice.module.css"

interface LoadingNoticeProps {
  readonly busy: boolean
  readonly label: string
}

export function LoadingNotice({ busy, label }: LoadingNoticeProps) {
  const visible = useLoadingIndicator(busy)
  return (
    <div className={styles.anchor}>
      <div
        className={styles.notice}
        data-state={visible ? "open" : "closed"}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        aria-hidden={!visible}
      >
        <span className={styles.indicator}>{visible && <Spinner />}</span>
        <span>{label}</span>
      </div>
    </div>
  )
}
