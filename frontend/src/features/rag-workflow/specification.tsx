import { useTranslation } from "react-i18next"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { Button } from "@/shared/ui/button"
import { BackendText } from "@/shared/ui/message"
import { CharacteristicField } from "./characteristic-field"
import { Extras } from "./extras"
import styles from "./specification.module.css"

export function Specification({
  flow,
  onPreview,
}: {
  readonly flow: RagWorkflowState
  readonly onPreview: () => void
}) {
  const { t } = useTranslation(["rag"])
  const session = flow.session
  if (!session?.position) return null
  const fixed = Object.entries(session.position.fixed)
  return (
    <section className={styles.spec}>
      <header>
        <p>{session.position.code}</p>
        <h2>{t("rag:specTitle")}</h2>
        <h3>
          <BackendText>{session.position.name}</BackendText>
        </h3>
      </header>
      {session.selection_reason && (
        <p role="status">
          <BackendText>{session.selection_reason}</BackendText>
        </p>
      )}
      {fixed.length > 0 && (
        <section>
          <h3>{t("rag:fixed")}</h3>
          <dl className={styles.fixed}>
            {fixed.map(([name, value]) => (
              <div key={name}>
                <dt>
                  <BackendText>{name}</BackendText>
                </dt>
                <dd>
                  <BackendText>{value}</BackendText>
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      <section className={styles.editable}>
        <h3>{t("rag:editable")}</h3>
        <div className={styles.fields}>
          {session.characteristics.map((field) => (
            <CharacteristicField
              key={field.name}
              field={field}
              busy={flow.busy}
              onChange={(values) => flow.values(field.name, values)}
            />
          ))}
        </div>
        {!session.characteristics.length && <p>{t("rag:noCharacteristics")}</p>}
      </section>
      <Extras flow={flow} />
      <div className={styles.footer}>
        <Button variant="ghost" icon="back" disabled={flow.busy} onClick={flow.back}>
          {t("rag:backGroups")}
        </Button>
        <div className={styles.actions}>
          {(flow.draft.trim() || session.missing.length > 0) && (
            <strong>
              {flow.draft.trim()
                ? t("rag:detailsPending")
                : t("rag:missingFields", { fields: session.missing.join(", ") })}
            </strong>
          )}
          <Button
            variant="primary"
            icon="next"
            disabled={flow.busy || session.missing.length > 0 || Boolean(flow.draft.trim())}
            onClick={onPreview}
          >
            {t("rag:preview")}
          </Button>
        </div>
      </div>
    </section>
  )
}
