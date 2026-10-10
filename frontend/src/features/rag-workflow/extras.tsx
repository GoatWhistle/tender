import { useState } from "react"
import { useTranslation } from "react-i18next"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { Button } from "@/shared/ui/button"
import { Field } from "@/shared/ui/field"
import { BackendText } from "@/shared/ui/message"
import styles from "./extras.module.css"

export function Extras({ flow }: { readonly flow: RagWorkflowState }) {
  const { t } = useTranslation(["rag"])
  const [name, setName] = useState("")
  const [value, setValue] = useState("")
  const [reason, setReason] = useState("")
  const session = flow.session
  if (!session) return null
  return (
    <section className={styles.extras}>
      <h3>{t("rag:extraTitle")}</h3>
      <p>{t(session.extras_allowed ? "rag:extraHint" : "rag:extraForbidden")}</p>
      {session.extras.map((extra, index) => (
        <div key={`${extra.name}-${extra.value}`} className={styles.item}>
          <div>
            <strong>
              <BackendText>{extra.name}</BackendText>
            </strong>
            <p>
              <BackendText>{extra.value}</BackendText>
            </p>
            <p>
              <BackendText>{extra.reason ?? ""}</BackendText>
            </p>
          </div>
          <Button variant="ghost" disabled={flow.busy} onClick={() => flow.removeExtra(index)}>
            {t("rag:extraRemove")}
          </Button>
        </div>
      ))}
      {session.extras_allowed && (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            if (!flow.busy)
              flow.addExtra({ name, value, reason }, () => {
                setName("")
                setValue("")
                setReason("")
              })
          }}
        >
          <div className={styles.fields}>
            <Field
              id="extra-name"
              label={t("rag:extraName")}
              value={name}
              required
              disabled={flow.busy}
              onChange={(event) => setName(event.target.value)}
            />
            <Field
              id="extra-value"
              label={t("rag:extraValue")}
              value={value}
              required
              disabled={flow.busy}
              onChange={(event) => setValue(event.target.value)}
            />
            <Field
              id="extra-reason"
              label={t("rag:extraReason")}
              value={reason}
              required
              disabled={flow.busy}
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
          <Button
            type="submit"
            icon="plus"
            disabled={flow.busy || !name.trim() || !value.trim() || !reason.trim()}
          >
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
                  setName(fixed.name)
                  setValue(fixed.value)
                  setReason(fixed.reason ?? "")
                }
              }}
            >
              {t("rag:extraFix")}
            </Button>
          )}
        </div>
      )}
    </section>
  )
}
