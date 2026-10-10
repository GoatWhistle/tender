import type { RefObject } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "@/shared/ui/button"
import styles from "./composer.module.css"

interface ComposerProps {
  readonly placeholder?: string
  readonly value: string
  readonly onChange: (value: string) => void
  readonly onSubmit: () => void
  readonly busy: boolean
  readonly started: boolean
  readonly inputRef: RefObject<HTMLTextAreaElement | null>
}

export function Composer({
  value,
  onChange,
  onSubmit,
  busy,
  started,
  inputRef,
  placeholder,
}: ComposerProps) {
  const { t } = useTranslation(["portal"])
  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <div className={styles.composer}>
        <textarea
          data-focus="container"
          ref={inputRef}
          rows={1}
          aria-label={t("portal:inputLabel")}
          maxLength={4000}
          disabled={busy}
          value={value}
          placeholder={
            placeholder ?? t(started ? "portal:clarifyPlaceholder" : "portal:placeholder")
          }
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault()
              if (value.trim().length >= 1 && !busy) onSubmit()
            }
          }}
        />
        <span className={styles.count}>{t("portal:limit", { count: value.length })}</span>
        <Button
          className={styles.send}
          type="submit"
          variant="primary"
          icon="send"
          title={t("portal:send")}
          aria-label={t("portal:send")}
          disabled={value.trim().length < 1 || busy}
        />
      </div>
    </form>
  )
}
