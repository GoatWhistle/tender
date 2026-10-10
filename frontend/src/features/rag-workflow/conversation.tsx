import { type RefObject, useId } from "react"
import { useTranslation } from "react-i18next"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { useDisclosureMotion } from "@/shared/motion/use-disclosure-motion"
import { Button } from "@/shared/ui/button"
import { Composer } from "@/shared/ui/composer"
import { BackendText } from "@/shared/ui/message"
import styles from "./conversation.module.css"

export function Conversation({
  flow,
  inputRef,
}: {
  readonly flow: RagWorkflowState
  readonly inputRef: RefObject<HTMLTextAreaElement | null>
}) {
  const { t } = useTranslation(["rag"])
  const messages = flow.session?.messages ?? []
  const latest = messages.at(-1)
  const historyId = useId()
  const history = useDisclosureMotion<HTMLElement>(false, "100%")
  return (
    <section className={styles.conversation} aria-label={t("rag:conversation")}>
      <div className={styles.feedback}>
        <p className={styles.reply} role="status" aria-live="polite">
          {latest ? <BackendText>{latest.text}</BackendText> : t("rag:conversationHint")}
        </p>
      </div>
      <div className={styles.historyClip}>
        {history.present && messages.length > 0 && (
          <section
            ref={history.ref}
            id={historyId}
            className={styles.history}
            aria-label={t("rag:conversationHistory")}
          >
            {messages.map((message) => (
              <p key={message.id}>
                <strong>{t(message.role === "user" ? "rag:you" : "rag:assistant")}</strong>
                <BackendText>{message.text}</BackendText>
              </p>
            ))}
          </section>
        )}
      </div>
      <Composer
        value={flow.draft}
        onChange={flow.setDraft}
        onSubmit={() => flow.describe(flow.draft, () => flow.setDraft(""))}
        busy={flow.busy}
        started
        inputRef={inputRef}
        placeholder={t("rag:conversationPlaceholder")}
        actions={
          messages.length > 0 && (
            <Button
              className={styles.historyToggle}
              variant="ghost"
              icon="history"
              title={t("rag:conversationHistory")}
              aria-label={t("rag:conversationHistory")}
              aria-expanded={history.open}
              aria-controls={historyId}
              onClick={history.toggle}
            />
          )
        }
      />
    </section>
  )
}
