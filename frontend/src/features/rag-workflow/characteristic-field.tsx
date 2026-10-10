import { useTranslation } from "react-i18next"
import type { Characteristic } from "@/entities/rag"
import { Button } from "@/shared/ui/button"
import { Disclosure } from "@/shared/ui/disclosure"
import { BackendText } from "@/shared/ui/message"
import styles from "./characteristic-field.module.css"
import { NumericCharacteristic } from "./numeric-characteristic/numeric-characteristic"

export function CharacteristicField({
  field,
  busy,
  onChange,
  onExactChange,
  onPending,
}: {
  readonly field: Characteristic
  readonly busy: boolean
  readonly onPending: (dirty: boolean) => void
  readonly onExactChange: (value: string) => void
  readonly onChange: (values: string[]) => void
}) {
  const { t } = useTranslation(["rag"])
  if (field.numeric)
    return (
      <NumericCharacteristic
        field={field}
        busy={busy}
        onChange={onExactChange}
        onPending={onPending}
      />
    )
  return (
    <div className={styles.field}>
      <div className={styles.label}>
        <BackendText>{field.name}</BackendText>
        {field.required && !field.values.length && <strong>{t("rag:required")}</strong>}
      </div>
      <Disclosure title={field.values.join("; ") || t("rag:selectValue")} status={null}>
        <fieldset className={styles.options} aria-label={field.name}>
          <p>{t(field.multiple ? "rag:many" : "rag:one")}</p>
          {field.options.map((option) => {
            const selected = field.values.includes(option)
            return (
              <Button
                key={option}
                variant={selected ? "secondary" : "ghost"}
                icon={selected ? "check" : "plus"}
                aria-pressed={selected}
                disabled={busy}
                onClick={() =>
                  onChange(
                    field.multiple
                      ? selected
                        ? field.values.filter((value) => value !== option)
                        : [...field.values, option]
                      : [option],
                  )
                }
              >
                <BackendText>{option}</BackendText>
              </Button>
            )
          })}
          {field.values.length > 0 && (
            <Button variant="ghost" disabled={busy} onClick={() => onChange([])}>
              {t("rag:clear")}
            </Button>
          )}
        </fieldset>
      </Disclosure>
    </div>
  )
}
