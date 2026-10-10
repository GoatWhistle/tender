import { useTranslation } from "react-i18next"
import type { Characteristic } from "@/entities/rag"
import { Icon } from "@/shared/ui/icon"
import styles from "./origin-badge.module.css"

type Origin = NonNullable<Characteristic["origin"]>

const icons = { description: "document", assistant: "message", manual: "user" } as const

export function OriginBadge({
  origin,
  compact = false,
}: {
  readonly origin: Origin
  readonly compact?: boolean
}) {
  const { t } = useTranslation(["rag"])
  const label = t(`rag:origin.${origin}`)
  return (
    <span className={styles.badge} data-origin={origin} title={label}>
      <Icon name={icons[origin]} size={14} />
      {compact ? <span className={styles.hidden}>{label}</span> : label}
    </span>
  )
}
