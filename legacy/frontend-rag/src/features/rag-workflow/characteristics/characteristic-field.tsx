import { useEffect, useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import type { Characteristic } from "@/entities/rag"
import { Button } from "@/shared/ui/button"
import { BackendText } from "@/shared/ui/message"
import { BandInput } from "./band-input"
import styles from "./characteristic-field.module.css"
import { BooleanSwitch, ChoiceChips, OptionSearch, RangeScale } from "./controls"
import { fieldKind, toggle } from "./field-kind"
import { OriginBadge } from "./origin-badge"

export function CharacteristicField({
  id,
  field,
  busy,
  onChange,
  onNumber,
}: {
  readonly id: string
  readonly field: Characteristic
  readonly busy: boolean
  readonly onChange: (values: string[]) => void
  readonly onNumber: (value: number | null) => void
}) {
  const { t, i18n } = useTranslation(["rag"])
  const format = useMemo(() => new Intl.NumberFormat(i18n.language).format, [i18n.language])
  const kind = fieldKind(field, format)
  const signature = field.values.join("\n")
  const previous = useRef(signature)
  const [flashes, setFlashes] = useState(0)
  useEffect(() => {
    if (previous.current === signature) return
    previous.current = signature
    setFlashes((count) => count + 1)
  }, [signature])
  const props = {
    name: field.name,
    values: field.values,
    busy,
    pick: (option: string) => onChange(toggle(field.values, option, field.multiple)),
  }
  const empty = field.values.length === 0
  return (
    <div id={id} className={styles.field} data-empty={empty} data-required={field.required}>
      {flashes > 0 && <span key={flashes} className={styles.flash} aria-hidden="true" />}
      <div className={styles.label}>
        <span className={styles.name}>
          <BackendText>{field.name}</BackendText>
        </span>
        {field.required && empty && <strong>{t("rag:required")}</strong>}
        {field.origin && <OriginBadge origin={field.origin} />}
        {field.multiple && <span className={styles.hint}>{t("rag:many")}</span>}
      </div>
      <div className={styles.control}>
        {kind.type === "boolean" && <BooleanSwitch {...props} yes={kind.yes} no={kind.no} />}
        {kind.type === "input" && (
          <BandInput
            values={field.values}
            number={field.number ?? null}
            bands={kind.bands}
            unit={kind.unit}
            busy={busy}
            format={format}
            onNumber={onNumber}
          />
        )}
        {kind.type === "range" && <RangeScale {...props} bands={kind.bands} unit={kind.unit} />}
        {kind.type === "number" && <RangeScale {...props} bands={kind.bands} unit={kind.unit} />}
        {kind.type === "search" && <OptionSearch {...props} options={field.options} />}
        {kind.type === "choice" && <ChoiceChips {...props} options={field.options} />}
        {!empty && kind.type !== "search" && kind.type !== "input" && (
          <Button
            variant="ghost"
            className={styles.clear}
            disabled={busy}
            onClick={() => onChange([])}
          >
            {t("rag:clear")}
          </Button>
        )}
      </div>
    </div>
  )
}
