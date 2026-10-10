import { useId, useState } from "react"
import { useTranslation } from "react-i18next"
import type { Characteristic } from "@/entities/rag"
import { Button } from "@/shared/ui/button"
import { Field } from "@/shared/ui/field"
import { BackendText } from "@/shared/ui/message"
import styles from "./numeric-characteristic.module.css"

interface NumericCharacteristicProps {
  readonly field: Characteristic
  readonly busy: boolean
  readonly onPending: (dirty: boolean) => void
  readonly onChange: (value: string) => void
}

export function NumericCharacteristic(props: NumericCharacteristicProps) {
  return <NumericInput key={props.field.numeric?.exact ?? ""} {...props} />
}

function NumericInput({ field, busy, onChange, onPending }: NumericCharacteristicProps) {
  const { t } = useTranslation(["rag"])
  const id = useId()
  const saved = field.numeric?.exact ?? ""
  const [value, setValue] = useState(saved)
  const [attempted, setAttempted] = useState(false)
  const normalized = value.trim().replace(",", ".")
  const number = Number(normalized)
  const validNumber = /^[+-]?\d+(?:\.\d+)?$/.test(normalized) && Number.isFinite(number)
  const fitsRange = field.numeric?.ranges.some(
    (range) =>
      (!range.concrete?.length || range.concrete.includes(number)) &&
      (range.min == null ||
        number > range.min ||
        (number === range.min && range.min_op !== "greater")) &&
      (range.max == null ||
        number < range.max ||
        (number === range.max && range.max_op !== "less")),
  )
  const fits =
    fitsRange &&
    (!field.numeric?.positive || number > 0) &&
    (!field.numeric?.integer || (Number.isInteger(number) && number >= 0))
  const error = normalized
    ? !validNumber
      ? "rag:numberInvalid"
      : !fits
        ? "rag:numberOutside"
        : null
    : null
  const dirty = value !== saved
  return (
    <form
      className={styles.field}
      onSubmit={(event) => {
        event.preventDefault()
        setAttempted(true)
        if (!busy && !error) {
          setValue(normalized ? String(number) : "")
          onChange(normalized)
        }
      }}
    >
      <Field
        id={id}
        label={field.name}
        suffix={field.numeric?.unit}
        inputMode="decimal"
        value={value}
        disabled={busy}
        placeholder={t("rag:exactNumber")}
        issue={attempted && Boolean(error)}
        onChange={(event) => {
          setValue(event.target.value)
          onPending(event.target.value !== saved)
          setAttempted(false)
        }}
      >
        {attempted && error ? (
          <strong role="alert">{t(error)}</strong>
        ) : (
          <>
            {field.required && !saved && <strong>{t("rag:exactMissing")}</strong>}
            <BackendText>{t("rag:catalogRange", { range: field.values.join("; ") })}</BackendText>
          </>
        )}
      </Field>
      {dirty && (
        <Button type="submit" icon="check" disabled={busy}>
          {t("rag:saveNumber")}
        </Button>
      )}
    </form>
  )
}
