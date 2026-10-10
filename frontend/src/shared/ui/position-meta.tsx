import { useTranslation } from "react-i18next"
import { BackendText } from "./message"
import styles from "./position-meta.module.css"

export function PositionMeta({
  code,
  okpd2,
  okpd2Name,
}: {
  readonly code: string
  readonly okpd2: string
  readonly okpd2Name?: string
}) {
  const { t } = useTranslation(["rag"])
  return (
    <dl className={styles.meta} aria-label={t("rag:positionMeta")}>
      <div>
        <dt>{t("rag:codeLabel")}</dt>
        <dd className={styles.code}>{code}</dd>
      </div>
      <div className={styles.wide}>
        <dt>{t("rag:okpdLabel")}</dt>
        <dd>
          <span className={styles.code}>{okpd2}</span>
          {okpd2Name && (
            <span className={styles.caption}>
              <BackendText>{okpd2Name}</BackendText>
            </span>
          )}
        </dd>
      </div>
    </dl>
  )
}
