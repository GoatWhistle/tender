import { useTranslation } from "react-i18next"
import type { RagSession } from "@/entities/rag"
import { CategoryIcon } from "@/shared/ui/category-icon/category-icon"
import { BackendText } from "@/shared/ui/message"
import styles from "./card-preview.module.css"
import { OriginBadge } from "./origin-badge"

export function CardPreview({ session }: { readonly session: RagSession }) {
  const { t } = useTranslation(["rag"])
  const position = session.position
  if (!position) return null
  return (
    <aside className={styles.preview} aria-label={t("rag:livePreview")}>
      <p className={styles.caption}>{t("rag:livePreview")}</p>
      <header>
        <CategoryIcon code={position.code} />
        <div>
          <strong>
            <BackendText>{position.name}</BackendText>
          </strong>
          <span>{position.code}</span>
        </div>
      </header>
      <dl>
        {session.characteristics.map((field) => (
          <div key={field.name} data-empty={!field.values.length}>
            <dt>
              <BackendText>{field.name}</BackendText>
            </dt>
            <dd>
              {field.values.length ? (
                <BackendText>{field.values.join("; ")}</BackendText>
              ) : (
                t(field.required ? "rag:required" : "rag:emptyValue")
              )}
              {field.origin && <OriginBadge origin={field.origin} compact />}
            </dd>
          </div>
        ))}
        {session.extras.map((extra) => (
          <div key={`${extra.name}-${extra.value}`}>
            <dt>
              <BackendText>{extra.name}</BackendText>
            </dt>
            <dd>
              <BackendText>{extra.value}</BackendText>
            </dd>
          </div>
        ))}
      </dl>
    </aside>
  )
}
