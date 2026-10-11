import { useState, type FormEvent } from "react";
import type { Question } from "../../../entities/rag";
import { t } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/button/button";
import { TextField } from "../../../shared/ui/field/text-field";
import styles from "./question-block.module.css";

export interface QuestionBlockProps {
  readonly question: Question;
  readonly busy: boolean;
  readonly onOption: (index: number) => void;
  readonly onText: (text: string) => void;
}

export function QuestionBlock({ question, busy, onOption, onText }: QuestionBlockProps) {
  const [text, setText] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim()) onText(text.trim());
  };
  return (
    <section className={styles.question} aria-labelledby="question-title">
      <div className={styles.head}>
        <span className={styles.eyebrow}>{t("seller:question.eyebrow")}</span>
        <h3 id="question-title" className={styles.title}>
          {question.name}
        </h3>
        <p className={styles.lead}>
          {t(question.multiple ? "seller:question.multiple" : "seller:question.single")}
        </p>
      </div>
      <ul className={styles.options}>
        {question.options.map((option, index) => (
          <li key={option}>
            <button
              type="button"
              className={styles.option}
              disabled={busy}
              onClick={() => onOption(index)}
            >
              <span className={styles.label}>{option}</span>
              {typeof question.counts[index] === "number" && (
                <span className={styles.count}>
                  {t("seller:question.count", { count: question.counts[index] ?? 0 })}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
      <form className={styles.free} onSubmit={submit}>
        <TextField
          label={t("seller:question.text")}
          placeholder={t("seller:question.textPlaceholder")}
          value={text}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
        />
        <Button type="submit" variant="secondary" disabled={busy || !text.trim()}>
          {t("seller:question.send")}
        </Button>
      </form>
    </section>
  );
}
