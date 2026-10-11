import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "@/shared/ui/button"
import { CategoryIcon } from "@/shared/ui/category-icon/category-icon"
import { Icon } from "@/shared/ui/icon"
import { BackendText } from "@/shared/ui/message"
import type { CatalogComparison, ComparisonRow } from "../catalog-comparison.queries"
import styles from "./comparison-table.module.css"
import { ValueList } from "./value-list"

export function ComparisonTable({
  comparison,
  current,
  stale,
  remove,
}: {
  readonly comparison: CatalogComparison
  readonly current: string
  readonly stale: boolean
  readonly remove: (code: string) => void
}) {
  const { t } = useTranslation("rag")
  const [onlyDifferences, setOnlyDifferences] = useState(false)
  const differing = comparison.rows.filter((row) => row.differs).length
  const rows = onlyDifferences ? comparison.rows.filter((row) => row.differs) : comparison.rows
  return (
    <section className={styles.comparison} aria-label={t("compare.title")} data-stale={stale}>
      <header className={styles.toolbar}>
        <h2>{t("compare.title")}</h2>
        <p>{t("compare.summary", { count: differing, total: comparison.rows.length })}</p>
        <Button
          variant="ghost"
          icon="rank"
          aria-pressed={onlyDifferences}
          onClick={() => setOnlyDifferences(!onlyDifferences)}
        >
          {t("compare.onlyDifferences")}
        </Button>
      </header>
      <div className={styles.scroll} tabIndex={0} role="region" aria-label={t("compare.table")}>
        <table>
          <thead>
            <tr>
              <th scope="col">{t("compare.characteristic")}</th>
              {comparison.positions.map((position) => (
                <th scope="col" key={position.code}>
                  <div className={styles.position}>
                    <CategoryIcon code={position.code} />
                    <a href={`/catalog/${encodeURIComponent(position.code)}`}>{position.code}</a>
                    <strong>
                      <BackendText>{position.name}</BackendText>
                    </strong>
                    {position.code === current ? (
                      <span className={styles.current}>{t("compare.current")}</span>
                    ) : (
                      <Button
                        variant="ghost"
                        icon="remove"
                        onClick={() => remove(position.code)}
                        aria-label={t("compare.remove", { code: position.code })}
                        title={t("compare.remove", { code: position.code })}
                      >
                        {t("compare.removeShort")}
                      </Button>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <Row
                key={`${row.field}-${row.name ?? ""}`}
                row={row}
                codes={comparison.positions.map((position) => position.code)}
              />
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className={styles.empty}>{t("compare.noDifferences")}</p>}
      </div>
    </section>
  )
}

function Row({ row, codes }: { readonly row: ComparisonRow; readonly codes: readonly string[] }) {
  const { t } = useTranslation("rag")
  return (
    <tr data-differs={row.differs}>
      <th scope="row">
        {row.field === "characteristic" ? (
          <BackendText>{row.name}</BackendText>
        ) : (
          t(row.field === "okpd2" ? "catalogOkpd" : "catalogUnits")
        )}
        {row.differs && (
          <span className={styles.badge}>
            <Icon name="alert" size={16} />
            {t("compare.differs")}
          </span>
        )}
      </th>
      {row.values.map((values, column) => (
        <td key={codes[column]}>
          {values === null ? (
            <span className={styles.missing}>{t("compare.missing")}</span>
          ) : (
            <ValueList values={values} />
          )}
        </td>
      ))}
    </tr>
  )
}
