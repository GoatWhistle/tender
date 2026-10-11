import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "./button"
import styles from "./candidate-differences.module.css"
import { BackendText } from "./message"
import { TextButton } from "./text-button"

export function CandidateDifferences({
  differences,
  compact = false,
}: {
  readonly compact?: boolean
  readonly differences: Record<string, string>
}) {
  const { t } = useTranslation(["rag"])
  const [expanded, setExpanded] = useState(false)
  const entries = Object.entries(differences)
  if (!entries.length) return null
  return (
    <div className={styles.comparison}>
      <dl>
        {(expanded ? entries : entries.slice(0, 3)).map(([name, value]) => (
          <div key={name}>
            <dt>
              <BackendText>{name}</BackendText>
            </dt>
            <DifferenceValue value={value} />
          </div>
        ))}
      </dl>
      {!compact && entries.length > 3 && (
        <Button
          variant="ghost"
          icon="expand"
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          {t(expanded ? "rag:lessDifferences" : "rag:moreDifferences", {
            count: entries.length - 3,
          })}
        </Button>
      )}
    </div>
  )
}

function DifferenceValue({ value }: { readonly value: string }) {
  const { t } = useTranslation(["rag"])
  const [open, setOpen] = useState(false)
  const long = value.length > 120
  return (
    <dd data-clamped={long && !open}>
      <strong>
        <BackendText>{value}</BackendText>
      </strong>
      {long && (
        <TextButton aria-expanded={open} onClick={() => setOpen(!open)}>
          {t(open ? "rag:valueLess" : "rag:valueMore")}
        </TextButton>
      )}
    </dd>
  )
}
