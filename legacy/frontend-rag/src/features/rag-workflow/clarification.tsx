import { useTranslation } from "react-i18next"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { Button } from "@/shared/ui/button"
import { CandidateDifferences } from "@/shared/ui/candidate-differences"
import { BackendText } from "@/shared/ui/message"
import styles from "./clarification.module.css"

export function Clarification({ flow }: { readonly flow: RagWorkflowState }) {
  const { t } = useTranslation(["rag"])
  const session = flow.session
  if (!session) return null
  const question = session.question
  return (
    <section className={styles.panel}>
      <h2>{t(session.stage === "pick" ? "rag:pickTitle" : "rag:clarifyTitle")}</h2>
      {session.stage === "failed" && (
        <p role="alert">
          <strong>{t("rag:failed")}</strong>
        </p>
      )}
      {session.selection_reason && (
        <p role="status">
          <BackendText>{session.selection_reason}</BackendText>
        </p>
      )}
      {question && (
        <div className={styles.question}>
          <h3>
            <BackendText>{question.name}</BackendText>
          </h3>
          <div className={styles.options}>
            {question.options.map((option, index) => (
              <Button
                key={option}
                disabled={flow.busy}
                onClick={() => flow.answer({ option: index + 1 })}
              >
                <BackendText>{option}</BackendText>
              </Button>
            ))}
          </div>
          <Button variant="ghost" disabled={flow.busy} onClick={() => flow.answer({ option: 0 })}>
            {t("rag:dontKnow")}
          </Button>
        </div>
      )}
      {session.candidates.length > 1 && (
        <div className={styles.candidates}>
          {session.candidates.map((candidate) => (
            <section key={candidate.code}>
              <h3>
                <BackendText>{candidate.name}</BackendText>
              </h3>
              <p>{candidate.code}</p>
              <CandidateDifferences differences={candidate.differences} />
              {session.stage === "pick" && (
                <Button icon="next" disabled={flow.busy} onClick={() => flow.pick(candidate.code)}>
                  {t("rag:choose")}
                </Button>
              )}
            </section>
          ))}
        </div>
      )}
      {session.message && (
        <p role="status">
          <BackendText>{session.message}</BackendText>
        </p>
      )}
      <Button variant="ghost" icon="back" disabled={flow.busy} onClick={flow.back}>
        {t("rag:backGroups")}
      </Button>
    </section>
  )
}
