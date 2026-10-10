import type { Question } from "../../../api/types";
import { t } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/button/button";
import { ChoiceList } from "../../../shared/ui/choice/choice-list";
import styles from "./question-block.module.css";

export interface QuestionBlockProps {
  readonly question: Question;
  readonly busy: boolean;
  readonly onAnswer: (optionId: string | null) => void;
  readonly compact?: boolean;
}

export function QuestionBlock({ question, busy, onAnswer, compact = false }: QuestionBlockProps) {
  return (
    <section className={compact ? styles.compact : styles.question} aria-label={question.text}>
      {!compact && <h3 className={styles.title}>{question.text}</h3>}
      <ChoiceList
        legend={question.text}
        options={question.options}
        value={[]}
        disabled={busy}
        onChange={([id]) => id && onAnswer(id)}
      />
      {question.allow_unknown && (
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => onAnswer(null)}>
          {t("seller:row.unknown")}
        </Button>
      )}
    </section>
  );
}
