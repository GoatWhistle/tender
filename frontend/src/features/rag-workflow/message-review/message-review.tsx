import { useTranslation } from "react-i18next"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { Button } from "@/shared/ui/button"
import { BackendText } from "@/shared/ui/message"
import styles from "./message-review.module.css"

export function MessageReview({
  flow,
  onEdit,
}: {
  readonly flow: RagWorkflowState
  readonly onEdit: () => void
}) {
  const { t } = useTranslation("rag")
  const review = flow.session?.message_review
  if (!review) return null
  const edited = flow.draft.trim() !== review.original
  return (
    <section className={styles.review} aria-label={t("messageReviewTitle")}>
      <h2>{t("messageReviewTitle")}</h2>
      {review.fixes.map((fix) => (
        <div className={styles.change} key={`${fix.before}-${fix.after}`}>
          <div>
            <span>{t("before")}</span>
            <del>
              <BackendText>{fix.before}</BackendText>
            </del>
          </div>
          <div>
            <span>{t("suggested")}</span>
            <strong>
              <BackendText>{fix.after}</BackendText>
            </strong>
          </div>
        </div>
      ))}
      {review.issues.map((issue) => (
        <p key={issue} role="alert">
          <strong>
            <BackendText>{issue}</BackendText>
          </strong>
        </p>
      ))}
      <div className={styles.actions}>
        {(edited || !review.issues.length) && (
          <Button
            variant="primary"
            icon="check"
            disabled={flow.busy || !flow.draft.trim()}
            onClick={() => (edited ? flow.describe(flow.draft) : flow.confirmMessage())}
          >
            {t(edited ? "checkMessage" : "applyMessage")}
          </Button>
        )}
        <Button icon="edit" onClick={onEdit}>
          {t("editDescription")}
        </Button>
      </div>
    </section>
  )
}
