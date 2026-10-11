import { useState } from "react"
import { useTranslation } from "react-i18next"
import { BackendText } from "@/shared/ui/message"
import { TextButton } from "@/shared/ui/text-button"
import styles from "./value-list.module.css"

const VISIBLE = 5

export function ValueList({ values }: { readonly values: readonly string[] }) {
  const { t } = useTranslation("rag")
  const [open, setOpen] = useState(false)
  if (!values.length) return <span className={styles.empty}>{t("emptyValue")}</span>
  const hidden = values.length - VISIBLE
  return (
    <div className={styles.values}>
      <ul>
        {(open ? values : values.slice(0, VISIBLE)).map((value) => (
          <li key={value}>
            <BackendText>{value}</BackendText>
          </li>
        ))}
      </ul>
      {hidden > 0 && (
        <TextButton aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? t("valueLess") : t("compare.moreValues", { count: hidden })}
        </TextButton>
      )}
    </div>
  )
}
