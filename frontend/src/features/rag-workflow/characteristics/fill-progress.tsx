import { useTranslation } from "react-i18next"
import styles from "./fill-progress.module.css"

const RADIUS = 20
const LENGTH = 2 * Math.PI * RADIUS

export function FillProgress({
  filled,
  total,
}: {
  readonly filled: number
  readonly total: number
}) {
  const { t } = useTranslation(["rag"])
  const share = total ? filled / total : 1
  return (
    <div className={styles.progress} role="img" aria-label={t("rag:progress", { filled, total })}>
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <circle className={styles.track} cx="24" cy="24" r={RADIUS} />
        <circle
          className={styles.value}
          cx="24"
          cy="24"
          r={RADIUS}
          strokeDasharray={LENGTH}
          strokeDashoffset={LENGTH * (1 - share)}
          data-complete={filled === total}
        />
      </svg>
      <span aria-hidden="true">
        {filled}
        <small>/{total}</small>
      </span>
    </div>
  )
}
