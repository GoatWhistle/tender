import clsx from "clsx"
import { useTranslation } from "react-i18next"
import logo from "./assets/portal-logo.svg"
import styles from "./brand.module.css"
export function Brand({ compact = false }: { readonly compact?: boolean }) {
  const { t } = useTranslation(["portal"])
  if (!compact)
    return (
      <img className={styles.logo} src={logo} alt={t("portal:title")} width={180} height={40} />
    )
  return (
    <div role="img" className={clsx(styles.brand, styles.compact)} aria-label={t("portal:title")}>
      <span className={styles.mark} aria-hidden="true">
        <span />
      </span>
    </div>
  )
}
