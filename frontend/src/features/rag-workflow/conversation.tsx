import type { RefObject } from "react"
import { useTranslation } from "react-i18next"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { Composer } from "@/shared/ui/composer"
import { Disclosure } from "@/shared/ui/disclosure"
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
  return (
    <section className={styles.conversation} aria-label={t("rag:conversation")}>
      <div className={styles.feedback}>
        <p className={styles.hint}>{t("rag:conversationHint")}</p>
        {messages.length > 0 && (
          <Disclosure title={t("rag:conversationHistory")} status={null}>
            <div className={styles.history}>
              {messages.map((message) => (
                <p key={message.id}>
                  <strong>{t(message.role === "user" ? "rag:you" : "rag:assistant")}</strong>
                  <BackendText>{message.text}</BackendText>
                </p>
              ))}
            </div>
          </Disclosure>
        )}
        {latest && (
          <p className={styles.reply} role="status" aria-live="polite">
            <BackendText>{latest.text}</BackendText>
          </p>
        )}
      </div>
      <Composer
        value={flow.draft}
        onChange={flow.setDraft}
        onSubmit={() => flow.describe(flow.draft)}
        busy={flow.busy}
        started
        inputRef={inputRef}
        placeholder={t("rag:conversationPlaceholder")}
      />
    </section>
  )
}
