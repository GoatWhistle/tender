import { useRef, type FormEvent, type KeyboardEvent } from "react";
import type { Fix } from "../../../entities/rag";
import { Collapse } from "../../../shared/motion";
import { t, type MessageKey } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/button/button";
import { TextArea } from "../../../shared/ui/field/text-area";
import { StatusBadge } from "../../../shared/ui/status-badge/status-badge";
import { MAX_TEXT, OPERATION_LABEL, type RagWizard } from "../model/use-rag-wizard";
import styles from "./describe-step.module.css";
import { StepLayout } from "./step-layout";

const EXAMPLES: readonly MessageKey[] = [
  "seller:describe.example1",
  "seller:describe.example2",
  "seller:describe.example3",
  "seller:describe.example4",
];

const FIX_LABEL: Record<string, MessageKey> = {
  typo: "seller:review.kind.typo",
  unit: "seller:review.kind.unit",
  logic: "seller:review.kind.logic",
  other: "seller:review.kind.other",
};

function FixItem({ fix }: { readonly fix: Fix }) {
  return (
    <li className={styles.fix}>
      <StatusBadge tone="warning" label={t(FIX_LABEL[fix.kind] ?? "seller:review.kind.other")} />
      <span className={styles.before}>{fix.before}</span>
      <span className={styles.arrow} aria-hidden="true" />
      <span className={styles.after}>{fix.after}</span>
    </li>
  );
}

export function DescribeStep({ wizard }: { readonly wizard: RagWizard }) {
  const { draft, busy, search, operation } = wizard;
  const field = useRef<HTMLTextAreaElement>(null);
  const length = draft.trim().length;
  const tooLong = length > MAX_TEXT;
  const review = search?.stage === "review" ? search : null;
  const unchanged = review !== null && draft.trim() === review.description;

  const onSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    if (review && unchanged) return wizard.confirm();
    wizard.submit();
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) onSubmit(e);
  };

  return (
    <form onSubmit={onSubmit} className={styles.form}>
      <StepLayout
        id="describe"
        heading={t("seller:describe.heading")}
        lead={t("seller:describe.lead")}
        busy={busy}
        status={operation ? t(OPERATION_LABEL[operation]) : undefined}
        next={
          <Button
            type="submit"
            variant="primary"
            pending={busy}
            disabled={!draft.trim() || tooLong}
          >
            {t(review && unchanged ? "seller:review.confirm" : "seller:describe.submit")}
          </Button>
        }
      >
        <Collapse open={Boolean(review)}>
          {review && (
            <section className={styles.review} aria-labelledby="review-title">
              <div className={styles.reviewHead}>
                <h3 id="review-title" className={styles.reviewTitle}>
                  {t(review.fixes.length ? "seller:review.title" : "seller:review.issuesTitle")}
                </h3>
                <p className={styles.reviewLead}>{t("seller:review.lead")}</p>
              </div>
              {review.fixes.length > 0 && (
                <ul className={styles.fixes}>
                  {review.fixes.map((fix) => (
                    <FixItem key={`${fix.before}-${fix.after}`} fix={fix} />
                  ))}
                </ul>
              )}
              {review.corrected !== review.description && (
                <div className={styles.corrected}>
                  <span className={styles.caption}>{t("seller:review.corrected")}</span>
                  <p>{review.corrected}</p>
                </div>
              )}
              {review.issues.length > 0 && (
                <div className={styles.issues}>
                  <span className={styles.caption}>{t("seller:review.issues")}</span>
                  <ul>
                    {review.issues.map((issue) => (
                      <li key={issue}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className={styles.reviewActions}>
                <Button variant="primary" disabled={busy} onClick={wizard.confirm}>
                  {t("seller:review.confirm")}
                </Button>
                <Button
                  variant="secondary"
                  icon="edit"
                  disabled={busy}
                  onClick={() => field.current?.focus()}
                >
                  {t("seller:review.edit")}
                </Button>
              </div>
            </section>
          )}
        </Collapse>
        <TextArea
          ref={field}
          id="describe"
          label={t("seller:describe.label")}
          size="lg"
          value={draft}
          autoFocus
          invalid={tooLong}
          placeholder={t("seller:describe.placeholder")}
          hint={
            length > MAX_TEXT * 0.9
              ? t("seller:describe.counter", { length, max: MAX_TEXT })
              : t("seller:describe.hint")
          }
          onChange={(e) => wizard.setDraft(e.target.value)}
          onKeyDown={onKeyDown}
        />
        {!review && (
          <div className={styles.examples}>
            <p className={styles.caption}>{t("seller:describe.examples")}</p>
            <ul className={styles.exampleList}>
              {EXAMPLES.map((key) => (
                <li key={key}>
                  <button
                    type="button"
                    className={styles.example}
                    onClick={() => wizard.setDraft(t(key))}
                  >
                    {t(key)}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </StepLayout>
    </form>
  );
}
