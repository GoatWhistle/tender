import { useTranslation } from "react-i18next"
import { Icon } from "@/shared/ui/icon"
import styles from "./stepper.module.css"
export function Stepper({
  current,
  complete = false,
  busy = false,
}: {
  readonly current: number
  readonly complete?: boolean
  readonly busy?: boolean
}) {
  const { t } = useTranslation(["portal"])
  const steps = t("portal:steps", { returnObjects: true })
  const from = busy ? Math.min(current, steps.length - 2) : -1
  return (
    <nav className={styles.nav} aria-label={t("portal:stepsLabel")}>
      <ol className={styles.steps}>
        {steps.map((label, index) => (
          <li
            key={label}
            className={styles.step}
            data-active={index === current && !complete}
            data-complete={index < current || complete}
            data-target={index === from + 1}
            aria-current={index === current ? "step" : undefined}
          >
            <span className={styles.circle}>
              {index < current || complete ? <Icon name="check" size={16} /> : index + 1}
            </span>
            <span className={styles.label}>{label}</span>
            {index === from && (
              <span className={styles.arrow} aria-hidden="true">
                <Icon name="chevron" size={22} />
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}
