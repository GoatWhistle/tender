import { useTranslation } from "react-i18next"
import { Icon } from "@/shared/ui/icon"
import styles from "./stepper.module.css"
export function Stepper({
  current,
  complete = false,
}: {
  readonly current: number
  readonly complete?: boolean
}) {
  const { t } = useTranslation(["portal"])
  const steps = t("portal:steps", { returnObjects: true })
  return (
    <nav className={styles.nav} aria-label={t("portal:stepsLabel")}>
      <ol className={styles.steps}>
        {steps.map((label, index) => (
          <li
            key={label}
            className={styles.step}
            data-active={index === current && !complete}
            data-complete={index < current || complete}
            aria-current={index === current ? "step" : undefined}
          >
            <span className={styles.circle}>
              {index < current || complete ? <Icon name="check" size={16} /> : index + 1}
            </span>
            <span>{label}</span>
            {index === current && !complete && index < steps.length - 1 && (
              <span className={styles.flow} aria-hidden="true" />
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}
