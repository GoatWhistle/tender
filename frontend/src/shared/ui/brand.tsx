import clsx from "clsx"
import { useTranslation } from "react-i18next"
import styles from "./brand.module.css"
export function Brand({ compact = false }: { readonly compact?: boolean }) {
  const { t } = useTranslation(["portal"])
  return (
    <div
      role="img"
      className={clsx(styles.brand, compact && styles.compact)}
      aria-label={t("portal:title")}
    >
      <span className={styles.mark} aria-hidden="true">
        <span />
      </span>
      {!compact && (
        <span className={styles.text}>
          <strong>{t("portal:brandTop")}</strong>
          <span>{t("portal:brandBottom")}</span>
        </span>
      )}
    </div>
  )
}
