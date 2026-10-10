import type { FormEvent, KeyboardEvent } from "react";
import { MAX_TEXT, textLength } from "../../../lib/sellerSession";
import { Collapse } from "../../../shared/motion";
import { t, type MessageKey } from "../../../shared/i18n";
import { Banner } from "../../../shared/ui/banner/banner";
import { Button } from "../../../shared/ui/button/button";
import { TextArea } from "../../../shared/ui/field/text-area";
import { diagnosticsOf } from "../model/rows";
import type { Wizard } from "../model/use-wizard";
import styles from "./describe-step.module.css";
import { MarkedText } from "./marked-text";
import { QuestionBlock } from "./question-block";
import { StepLayout } from "./step-layout";

const EXAMPLES: readonly MessageKey[] = [
  "seller:describe.example1",
  "seller:describe.example2",
  "seller:describe.example3",
  "seller:describe.example4",
];

export function DescribeStep({ wizard }: { readonly wizard: Wizard }) {
  const { view, store, submit, goTo, answer } = wizard;
  const { state, draft, busy } = view;
  const sent = state?.messages ?? [];
  const length = textLength(draft.trim());
  const tooLong = length > MAX_TEXT;
  const appending = sent.length > 0;
  const canContinue = Boolean(state?.path) && !draft.trim();
  const unresolved = state && !state.path && state.status !== "technical_error" ? state : null;
  const purpose = unresolved?.next_question ?? null;

  const onSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    if (canContinue) return goTo(1);
    void submit();
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) onSubmit(e);
  };

  return (
    <form onSubmit={onSubmit} className={styles.form}>
      <StepLayout
        id="describe"
        heading={t(appending ? "seller:describe.append" : "seller:describe.heading")}
        lead={appending ? undefined : t("seller:describe.lead")}
        busy={busy}
        next={
          <Button
            type="submit"
            variant="primary"
            pending={busy}
            disabled={!draft.trim() && !canContinue}
          >
            {canContinue
              ? t("common:actions.next")
              : t(appending ? "seller:describe.appendSubmit" : "seller:describe.submit")}
          </Button>
        }
      >
        {appending && state && (
          <section className={styles.sent} aria-label={t("seller:describe.sent")}>
            <p className={styles.caption}>{t("seller:describe.sent")}</p>
            <ol className={styles.messages}>
              {sent.map((m) => (
                <li key={m.id} className={styles.message}>
                  <MarkedText
                    text={m.text}
                    marks={diagnosticsOf(state)
                      .map((d) => d.diagnostic)
                      .filter((d) => d.source.message_id === m.id)}
                  />
                </li>
              ))}
            </ol>
          </section>
        )}
        <Collapse open={Boolean(unresolved && !purpose)}>
          <Banner tone="warning" title={t("seller:describe.notFound")} live>
            {t("seller:describe.notFoundText")}
          </Banner>
        </Collapse>
        <Collapse open={Boolean(purpose)}>
          {purpose && (
            <QuestionBlock question={purpose} busy={busy} onAnswer={(id) => void answer(id)} />
          )}
        </Collapse>
        <TextArea
          id="describe"
          label={t(appending ? "seller:describe.append" : "seller:describe.label")}
          size={appending ? "md" : "lg"}
          value={draft}
          autoFocus
          invalid={tooLong}
          placeholder={t(
            appending ? "seller:describe.appendPlaceholder" : "seller:describe.placeholder",
          )}
          hint={
            length > MAX_TEXT * 0.9
              ? t("seller:describe.counter", { length, max: MAX_TEXT })
              : t("seller:describe.hint")
          }
          onChange={(e) => store.setDraft(e.target.value)}
          onKeyDown={onKeyDown}
        />
        {!appending && (
          <div className={styles.examples}>
            <p className={styles.caption}>{t("seller:describe.examples")}</p>
            <ul className={styles.exampleList}>
              {EXAMPLES.map((key) => (
                <li key={key}>
                  <button
                    type="button"
                    className={styles.example}
                    onClick={() => store.setDraft(t(key))}
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
