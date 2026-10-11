import { useTranslation } from "react-i18next"
import type { CatalogFound } from "@/entities/catalog-comparison"
import { Button } from "@/shared/ui/button"
import { CategoryIcon } from "@/shared/ui/category-icon/category-icon"
import { BackendText } from "@/shared/ui/message"
import styles from "./found-list.module.css"

export function FoundList({
  found,
  selected,
  full,
  stale,
  add,
}: {
  readonly found: readonly CatalogFound[]
  readonly selected: readonly string[]
  readonly full: boolean
  readonly stale: boolean
  readonly add: (code: string) => void
}) {
  const { t } = useTranslation("rag")
  return (
    <ul className={styles.list} data-stale={stale}>
      {found.map((position) => {
        const added = selected.includes(position.code)
        return (
          <li key={position.code} className={styles.row}>
            <CategoryIcon code={position.code} />
            <div className={styles.identity}>
              <BackendText>{position.name}</BackendText>
              <span>
                <a
                  href={`/catalog/${encodeURIComponent(position.code)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={t("catalogNewTab")}
                >
                  {position.code}
                </a>
                <BackendText>{position.okpd2_name}</BackendText>
              </span>
            </div>
            <Button
              icon={added ? "check" : "plus"}
              disabled={added || full}
              onClick={() => add(position.code)}
              aria-label={t(added ? "compare.added" : "compare.addPosition", {
                code: position.code,
              })}
            >
              {t(added ? "compare.addedShort" : "compare.addShort")}
            </Button>
          </li>
        )
      })}
    </ul>
  )
}
