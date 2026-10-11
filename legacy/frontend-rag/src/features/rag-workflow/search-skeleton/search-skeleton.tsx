import type { CSSProperties } from "react"
import { useTranslation } from "react-i18next"
import { useShuffleMotion } from "@/shared/motion/use-shuffle-motion"
import styles from "./search-skeleton.module.css"

const widths = ["72%", "48%", "64%", "56%", "80%", "44%"]

export function SearchSkeleton() {
  const { t } = useTranslation(["portal"])
  const { order, listRef } = useShuffleMotion(widths.length)
  return (
    <section className={styles.skeleton}>
      <h2>{t("portal:searchingTitle")}</h2>
      <ol ref={listRef} className={styles.list} aria-hidden="true">
        {order.map((row) => (
          <li key={row} data-id={row} style={{ "--bar": widths[row], "--i": row } as CSSProperties}>
            <span className={styles.number} />
            <span className={styles.icon} />
            <span className={styles.lines}>
              <span className={styles.name} />
              <span className={styles.code} />
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}
