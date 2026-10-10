import { useId, useState } from "react"
import { useTranslation } from "react-i18next"
import { Field } from "@/shared/ui/field"
import { Icon } from "@/shared/ui/icon"
import styles from "./band-input.module.css"
import { bandLabel, type Doubt, doubt, type KtruBand, matchBand } from "./field-kind"

const DOUBTS: Record<Doubt, "rag:doubtLarge" | "rag:doubtSmall" | "rag:doubtNegative"> = {
  large: "rag:doubtLarge",
  small: "rag:doubtSmall",
  negative: "rag:doubtNegative",
}

export interface BandInputProps {
  readonly values: readonly string[]
  readonly number: number | null
  readonly bands: readonly KtruBand[]
  readonly unit: string
  readonly busy: boolean
  readonly format: (value: number) => string
  readonly onNumber: (value: number | null) => void
}

function parse(text: string) {
  const clean = text.replace(/\s/g, "").replace(",", ".")
  if (!clean) return null
  const value = Number(clean)
  return Number.isFinite(value) ? value : Number.NaN
}

function span(bands: readonly KtruBand[]) {
  const low = bands[0]?.min
  const high = bands.at(-1)?.max
  if (low === null || low === undefined || high === null || high === undefined) return null
  return { low, high }
}

export function BandInput({ values, number, bands, unit, busy, format, onNumber }: BandInputProps) {
  const { t } = useTranslation(["rag"])
  const id = useId()
  const [text, setText] = useState<string | null>(null)
  const [seen, setSeen] = useState(number)
  if (seen !== number) {
    setSeen(number)
    setText(null)
  }
  const shown = text ?? (number === null ? "" : String(number))
  const value = parse(shown)
  const band = value === null || Number.isNaN(value) ? null : matchBand(bands, value)
  const chosen = bands.find((item) => item.option === values[0])
  const invalid = value !== null && (Number.isNaN(value) || !band)
  const limits = span(bands)
  const range = limits && { low: format(limits.low), high: format(limits.high) }
  const suspect = band && value !== null ? doubt(bands, value) : null
  const beyond = limits !== null && value !== null && (value < limits.low || value > limits.high)
  function commit() {
    if (text === null || busy) return
    if (value === null) {
      if (values.length) onNumber(null)
      return
    }
    if (band && value !== number) onNumber(value)
  }
  const help = () => {
    if (value !== null && Number.isNaN(value)) return t("rag:numberInvalid")
    if (value !== null && !band)
      return range && beyond ? t("rag:numberOutsideSpan", range) : t("rag:numberOutside")
    if (band) return t("rag:numberBand", { band: bandLabel(band, format) })
    if (chosen) return t("rag:numberChosen", { band: bandLabel(chosen, format) })
    return range ? t("rag:numberSpan", range) : t("rag:numberHint")
  }
  return (
    <div className={styles.input}>
      <Field
        id={id}
        label={t("rag:numberLabel")}
        suffix={unit || undefined}
        issue={invalid}
        inputMode="decimal"
        autoComplete="off"
        value={shown}
        readOnly={busy}
        onChange={(event) => setText(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") commit()
        }}
      >
        <p className={styles.help} data-invalid={invalid} role={invalid ? "alert" : undefined}>
          {help()}
        </p>
        {suspect && (
          <p className={styles.doubt} role="status">
            <Icon name="alert" size={16} />
            {t(DOUBTS[suspect.code], { edge: format(suspect.edge), unit })}
          </p>
        )}
      </Field>
    </div>
  )
}
