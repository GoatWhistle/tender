import { useState } from "react"
import { useTranslation } from "react-i18next"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { Button } from "@/shared/ui/button"
import { Field } from "@/shared/ui/field"
import { BackendText } from "@/shared/ui/message"
import styles from "./extras.module.css"
import { Suggestions } from "./suggestions"

function parse(line: string) {
  const match = /^([^=:]+)[=:](.+)$/.exec(line)
  return { name: match?.[1]?.trim() ?? "", value: match?.[2]?.trim() ?? "" }
}

export function Extras({ flow }: { readonly flow: RagWorkflowState }) {
  const { t } = useTranslation(["rag"])
  const [line, setLine] = useState("")
  const [reason, setReason] = useState("")
  const session = flow.session
  if (!session) return null
  const { name, value } = parse(line)
  return (
    <section className={styles.extras}>
      <h3>{t("rag:extraTitle")}</h3>
      <p>{t(session.extras_allowed ? "rag:extraHint" : "rag:extraForbidden")}</p>
      {session.extras.length > 0 && (
        <ul className={styles.list}>
          {session.extras.map((extra, index) => (
            <li key={`${extra.name}-${extra.value}`} className={styles.item}>
              <div>
                <strong>
                  <BackendText>{extra.name}</BackendText>
                </strong>
                <span>
                  <BackendText>{extra.value}</BackendText>
                </span>
                {extra.reason && (
                  <p>
                    <BackendText>{extra.reason}</BackendText>
                  </p>
                )}
              </div>
              <Button
                variant="ghost"
                icon="close"
                disabled={flow.busy}
                aria-label={t("rag:extraRemoveNamed", { name: extra.name })}
                onClick={() => flow.removeExtra(index)}
              />
            </li>
          ))}
        </ul>
      )}
      <Suggestions
        flow={flow}
        custom={(text) => {
          setLine(text)
          document.getElementById("extra-line")?.focus()
        }}
      />
      {session.extras_allowed && (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            if (!flow.busy && name && value)
              flow.addExtra({ name, value, reason: reason.trim() }, () => {
                setLine("")
                setReason("")
              })
          }}
        >
          <div className={styles.fields}>
            <Field
              id="extra-line"
              label={t("rag:extraLine")}
              placeholder={t("rag:extraLinePlaceholder")}
              value={line}
              required
              disabled={flow.busy}
              onChange={(event) => setLine(event.target.value)}
              issue={Boolean(line.trim()) && !(name && value)}
            >
              {line.trim() && !(name && value) ? t("rag:extraLineHint") : null}
            </Field>
            <Field
              id="extra-reason"
              label={t("rag:extraReasonOptional")}
              value={reason}
              disabled={flow.busy}
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
          <Button type="submit" icon="plus" disabled={flow.busy || !name || !value}>
            {t("rag:extraAdd")}
          </Button>
        </form>
      )}
      {flow.verdict && !flow.verdict.accepted && (
        <div role="alert" className={styles.verdict}>
          {flow.verdict.problems.map((problem) => (
            <p key={problem}>
              <strong>
                <BackendText>{problem}</BackendText>
              </strong>
            </p>
          ))}
          {flow.verdict.fixed && (
            <Button
              icon="edit"
              disabled={flow.busy}
              onClick={() => {
                const fixed = flow.verdict?.fixed
                if (fixed) {
                  setLine(`${fixed.name} = ${fixed.value}`)
                  setReason(fixed.reason ?? "")
                }
              }}
            >
              {t("rag:extraFix")}
            </Button>
          )}
        </div>
      )}
      {flow.verdict?.accepted && flow.verdict.warnings.length > 0 && (
        <div role="status" className={styles.verdict}>
          {flow.verdict.warnings.map((warning) => (
            <p key={warning}>
              <BackendText>{warning}</BackendText>
            </p>
          ))}
        </div>
      )}
    </section>
  )
}
