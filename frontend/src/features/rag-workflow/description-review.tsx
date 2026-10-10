import { useTranslation } from "react-i18next"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { Button } from "@/shared/ui/button"
import { BackendText } from "@/shared/ui/message"
import styles from "./description-review.module.css"

export function DescriptionReview({
  flow,
  onEdit,
}: {
  readonly flow: RagWorkflowState
  readonly onEdit: () => void
}) {
  const { t } = useTranslation("rag")
  const search = flow.search
  if (!search) return null
  const edited = flow.draft.trim() !== search.description
  return (
    <section className={styles.review} aria-labelledby="description-review-title">
      <header>
        <h2 id="description-review-title">
          {t(search.fixes.length ? "reviewChanges" : "questions")}
        </h2>
      </header>
      <div className={styles.changes}>
        {search.fixes.map((fix) => (
          <div className={styles.change} key={`${fix.before}-${fix.after}`}>
            <div className={styles.before}>
              <span>{t("before")}</span>
              <del>
                <BackendText>{fix.before}</BackendText>
              </del>
            </div>
            <div className={styles.after}>
              <span>{t("suggested")}</span>
              <strong>
                <BackendText>{fix.after}</BackendText>
              </strong>
            </div>
          </div>
        ))}
      </div>
      {search.issues.map((issue) => (
        <p className={styles.issue} key={issue}>
          <strong>
            <BackendText>{issue}</BackendText>
          </strong>
        </p>
      ))}
      <div className={styles.actions}>
        <Button
          variant="primary"
          icon="check"
          disabled={flow.busy || flow.draft.trim().length < 3}
          onClick={flow.confirm}
        >
          {t(edited ? "checkEdits" : search.fixes.length ? "acceptChanges" : "searchAsIs")}
        </Button>
        <Button variant="secondary" icon="edit" disabled={flow.busy} onClick={onEdit}>
          {t("editDescription")}
        </Button>
      </div>
    </section>
  )
}
