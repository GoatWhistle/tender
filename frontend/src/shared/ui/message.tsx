import clsx from "clsx"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Brand } from "./brand"
import { Icon } from "./icon"
import styles from "./message.module.css"
export function Message({
  children,
  user = false,
}: {
  readonly children: ReactNode
  readonly user?: boolean
}) {
  const { t } = useTranslation(["portal"])
  return (
    <div className={clsx(styles.message, user && styles.user)}>
      <div role="img" aria-label={t(user ? "portal:user" : "portal:assistant")}>
        {user ? (
          <span className={styles.avatar}>
            <Icon name="user" />
          </span>
        ) : (
          <Brand compact />
        )}
      </div>
      <div className={styles.bubble}>{children}</div>
    </div>
  )
}
export function BackendText({ children }: { readonly children: ReactNode }) {
  return <span lang="ru">{children}</span>
}
