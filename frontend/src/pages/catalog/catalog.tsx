import { useTranslation } from "react-i18next"
import { useParams } from "react-router"
import { CatalogPosition } from "@/entities/catalog-position/catalog-position"
import { Icon } from "@/shared/ui/icon"
import styles from "./catalog.module.css"

export function CatalogPage() {
  const { code = "" } = useParams()
  const { t } = useTranslation("rag")
  return (
    <section className={styles.page} aria-label={t("catalogContents")}>
      <a className={styles.back} href="/">
        <Icon name="back" />
        {t("catalogBack")}
      </a>
      <CatalogPosition code={code} />
    </section>
  )
}
