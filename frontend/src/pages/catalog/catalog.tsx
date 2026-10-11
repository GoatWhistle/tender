import { useTranslation } from "react-i18next"
import { useParams, useSearchParams } from "react-router"
import { ComparisonTable, useCatalogComparison } from "@/entities/catalog-comparison"
import { CatalogPosition } from "@/entities/catalog-position/catalog-position"
import { ComparePicker } from "@/features/catalog-compare"
import { Spinner } from "@/shared/motion/primitives"
import { Button } from "@/shared/ui/button"
import { Icon } from "@/shared/ui/icon"
import { LoadStatus } from "@/shared/ui/load-status"
import styles from "./catalog.module.css"

const LIMIT = 4

export function CatalogPage() {
  const { code = "" } = useParams()
  const { t } = useTranslation("rag")
  const [params, setParams] = useSearchParams()
  const others = (params.get("compare") ?? "").split(",").filter((other) => other && other !== code)
  const codes = [...new Set([code, ...others])].slice(0, LIMIT)
  const comparison = useCatalogComparison(codes)
  function update(next: readonly string[]) {
    setParams(next.length ? { compare: next.join(",") } : {}, { replace: true })
  }
  return (
    <section className={styles.page} aria-label={t("catalogContents")}>
      <a className={styles.back} href="/">
        <Icon name="back" />
        {t("catalogBack")}
      </a>
      <div className={styles.stack}>
        <ComparePicker
          selected={codes}
          full={codes.length >= LIMIT}
          add={(added) => update([...codes.slice(1), added])}
        />
        {codes.length < 2 ? (
          <CatalogPosition code={code} />
        ) : comparison.data ? (
          <ComparisonTable
            comparison={comparison.data}
            current={code}
            stale={comparison.isPlaceholderData}
            remove={(removed) => update(codes.slice(1).filter((other) => other !== removed))}
          />
        ) : comparison.isError ? (
          <LoadStatus alert>
            <p>{t("compare.error")}</p>
            <Button onClick={() => void comparison.refetch()}>{t("catalogRetry")}</Button>
          </LoadStatus>
        ) : (
          <LoadStatus>
            <Spinner />
            {t("compare.loading")}
          </LoadStatus>
        )}
      </div>
    </section>
  )
}
