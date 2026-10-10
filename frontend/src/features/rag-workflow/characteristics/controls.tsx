import { useId, useState } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "@/shared/ui/button"
import { Icon } from "@/shared/ui/icon"
import { BackendText } from "@/shared/ui/message"
import styles from "./controls.module.css"
import type { Band } from "./field-kind"

const DENSE_FROM = 10
const collator = new Intl.Collator(undefined, { numeric: true })

interface ControlProps {
  readonly name: string
  readonly values: readonly string[]
  readonly busy: boolean
  readonly pick: (option: string) => void
}

export function ChoiceChips({
  name,
  values,
  busy,
  pick,
  options,
}: ControlProps & { readonly options: readonly string[] }) {
  return (
    <fieldset className={styles.chips} aria-label={name}>
      {options.map((option) => {
        const selected = values.includes(option)
        return (
          <Button
            key={option}
            className={styles.chip}
            icon={selected ? "check" : undefined}
            aria-pressed={selected}
            disabled={busy}
            onClick={() => pick(option)}
          >
            <BackendText>{option}</BackendText>
          </Button>
        )
      })}
    </fieldset>
  )
}

export function BooleanSwitch({
  name,
  values,
  busy,
  pick,
  yes,
  no,
}: ControlProps & { readonly yes: string; readonly no: string }) {
  return (
    <fieldset className={styles.segmented} aria-label={name}>
      {(
        [
          [yes, "check"],
          [no, "close"],
        ] as const
      ).map(([option, icon]) => (
        <Button
          key={option}
          icon={icon}
          aria-pressed={values.includes(option)}
          disabled={busy}
          onClick={() => pick(option)}
        >
          <BackendText>{option}</BackendText>
        </Button>
      ))}
    </fieldset>
  )
}

export function RangeScale({
  name,
  values,
  busy,
  pick,
  bands,
  unit,
}: ControlProps & { readonly bands: readonly Band[]; readonly unit: string }) {
  return (
    <fieldset className={styles.scale} aria-label={name}>
      <div className={styles.bands} data-dense={bands.length > DENSE_FROM}>
        {bands.map((band, index) => (
          <button
            key={band.option}
            type="button"
            className={styles.band}
            aria-pressed={values.includes(band.option)}
            aria-label={band.option}
            disabled={busy}
            onClick={() => pick(band.option)}
          >
            <span
              className={styles.bar}
              style={{ transform: `scaleY(${(index + 1) / bands.length})` }}
            />
            <span className={styles.bandLabel}>{band.label}</span>
          </button>
        ))}
      </div>
      {unit && (
        <p className={styles.unit}>
          <BackendText>{unit}</BackendText>
        </p>
      )}
    </fieldset>
  )
}

export function OptionSearch({
  name,
  values,
  busy,
  pick,
  options,
}: ControlProps & { readonly options: readonly string[] }) {
  const { t } = useTranslation(["rag"])
  const id = useId()
  const [query, setQuery] = useState("")
  const needle = query.trim().toLowerCase()
  const found = options
    .filter((option) => !values.includes(option) && option.toLowerCase().includes(needle))
    .sort(collator.compare)
  return (
    <div className={styles.search}>
      {values.length > 0 && (
        <ChoiceChips name={name} values={values} busy={busy} pick={pick} options={values} />
      )}
      <label className={styles.query} htmlFor={id}>
        <Icon name="search" size={16} />
        <span className={styles.hidden}>{t("rag:searchOption", { name })}</span>
        <input
          id={id}
          value={query}
          placeholder={t("rag:searchPlaceholder", { count: options.length })}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      <div className={styles.results}>
        {found.map((option) => (
          <Button
            key={option}
            className={styles.chip}
            aria-pressed={false}
            disabled={busy}
            onClick={() => pick(option)}
          >
            <BackendText>{option}</BackendText>
          </Button>
        ))}
        {!found.length && <p>{t("rag:searchEmpty")}</p>}
      </div>
    </div>
  )
}
