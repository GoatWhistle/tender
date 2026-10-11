import { useDeferredValue, useId, useState } from "react"
import { useTranslation } from "react-i18next"
import { type FindMode, useCatalogFind } from "@/entities/catalog-comparison"
import { Spinner } from "@/shared/motion/primitives"
import { Button } from "@/shared/ui/button"
import { Field } from "@/shared/ui/field"
import styles from "./compare-picker.module.css"
import { FoundList } from "./found-list"

const MODES: Record<FindMode, "compare.modeText" | "compare.modeSemantic"> = {
  text: "compare.modeText",
  semantic: "compare.modeSemantic",
}

export function ComparePicker({
  selected,
  full,
  add,
}: {
  readonly selected: readonly string[]
  readonly full: boolean
  readonly add: (code: string) => void
}) {
  const { t } = useTranslation("rag")
  const id = useId()
  const [mode, setMode] = useState<FindMode>("text")
  const [text, setText] = useState("")
  const [submitted, setSubmitted] = useState("")
  const [open, setOpen] = useState(true)
  const deferred = useDeferredValue(text)
  const query = useCatalogFind(mode === "text" ? deferred : submitted, mode)
  const searched = open && (mode === "text" ? deferred : submitted).trim().length >= 2
  return (
    <section className={styles.picker} aria-label={t("compare.add")}>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault()
          setSubmitted(text)
          setOpen(true)
        }}
      >
        <Field
          id={id}
          label={t("compare.add")}
          value={text}
          autoComplete="off"
          placeholder={t(
            mode === "text" ? "compare.placeholderText" : "compare.placeholderSemantic",
          )}
          onChange={(event) => {
            setText(event.target.value)
            setOpen(true)
          }}
        >
          {full ? t("compare.full") : t("compare.hint")}
        </Field>
        <fieldset className={styles.modes} aria-labelledby={`${id}-mode`}>
          <span id={`${id}-mode`}>{t("compare.mode")}</span>
          {(Object.keys(MODES) as FindMode[]).map((key) => (
            <Button
              key={key}
              variant="ghost"
              aria-pressed={mode === key}
              onClick={() => {
                setMode(key)
                setSubmitted("")
                setOpen(true)
              }}
            >
              {t(MODES[key])}
            </Button>
          ))}
        </fieldset>
        {mode === "semantic" && (
          <Button
            type="submit"
            variant="primary"
            icon="search"
            pending={query.isFetching}
            disabled={text.trim().length < 2}
          >
            {t("compare.find")}
          </Button>
        )}
      </form>
      {searched && (
        <div className={styles.results} aria-live="polite">
          {query.isPending && query.fetchStatus === "fetching" && (
            <p className={styles.status}>
              <Spinner />
              {t(mode === "semantic" ? "compare.searchingSemantic" : "compare.searching")}
            </p>
          )}
          {query.isError && <p className={styles.status}>{t("compare.findError")}</p>}
          {query.data && !query.data.length && (
            <p className={styles.status}>{t("compare.notFound")}</p>
          )}
          {query.data && query.data.length > 0 && (
            <FoundList
              found={query.data}
              selected={selected}
              full={full}
              stale={query.isPlaceholderData}
              add={(code) => {
                add(code)
                setOpen(false)
              }}
            />
          )}
        </div>
      )}
    </section>
  )
}
