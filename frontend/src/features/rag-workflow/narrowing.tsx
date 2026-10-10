import { useTranslation } from "react-i18next"
import { BackendText } from "@/shared/ui/message"
import styles from "./narrowing.module.css"
import type { NarrowingStep } from "./use-narrowing"

function share(step: NarrowingStep): string {
  const from = step.before || step.after || 1
  return `${Math.max(4, Math.round((step.after / from) * 100))}%`
}

export function Narrowing({
  steps,
  start,
  left,
}: {
  readonly steps: readonly NarrowingStep[]
  readonly start: number
  readonly left: number
}) {
  const { t } = useTranslation(["rag"])
  if (!steps.length) return null
  return (
    <section className={styles.narrowing} aria-label={t("rag:narrowingTitle")}>
      <header>
        <h3>{t("rag:narrowingTitle")}</h3>
        <p>{t("rag:narrowingLeft", { count: left })}</p>
      </header>
      <ol className={styles.steps}>
        <li className={styles.origin}>
          <span>{t("rag:narrowingStart", { count: start })}</span>
        </li>
        {steps.map((step) => (
          <li key={step.label}>
            <div className={styles.head}>
              <span className={styles.label}>
                <BackendText>{step.label}</BackendText>
              </span>
              <span className={styles.figure}>
                {step.before} <span aria-hidden="true">→</span> <strong>{step.after}</strong>
              </span>
            </div>
            <div className={styles.track}>
              <span className={styles.fill} style={{ width: share(step) }} />
            </div>
            <p className={styles.note}>
              {step.before > step.after
                ? t("rag:narrowingDropped", { count: step.before - step.after })
                : t("rag:narrowingKept")}
            </p>
          </li>
        ))}
      </ol>
    </section>
  )
}
