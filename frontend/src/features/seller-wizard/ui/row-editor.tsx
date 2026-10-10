import type { FactMutation } from "../../../api/types";
import type { PositionDetail } from "../../../entities/position";
import { t } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/button/button";
import type { CharacteristicRow, IndexedDiagnostic } from "../model/rows";
import type { Wizard } from "../model/use-wizard";
import { BindEditor } from "./bind-editor";
import { ProposalEditor } from "./proposal-editor";
import { QuestionBlock } from "./question-block";
import styles from "./row-editor.module.css";
import { ValueEditor } from "./value-editor";

export interface RowEditorProps {
  readonly row: CharacteristicRow;
  readonly wizard: Wizard;
  readonly position: PositionDetail | null;
  readonly onDone: () => void;
}

const NUMERIC = /^([+-]?[0-9.,]+)\s*(мм|см|м|кг|г|л|мл|Вт|кВт|шт)$/;

function suggestionBody(row: CharacteristicRow, { diagnostic: d, index }: IndexedDiagnostic) {
  const numeric = d.suggestion?.match(NUMERIC);
  return {
    action: "accept_suggestion",
    diagnostic_index: index,
    characteristic_name: row.facts[0]?.characteristic_name ?? row.name,
    raw_value: numeric?.[1] ?? d.suggestion ?? "",
    raw_unit: numeric?.[2] ?? null,
    kind: numeric ? "number" : "text",
  } as const;
}

export function RowEditor({ row, wizard, position, onDone }: RowEditorProps) {
  const { view, store, mutate } = wizard;
  const state = view.state;
  if (!state) return null;
  const busy = view.busy;
  const fact = row.facts[0] ?? null;
  const related = row.facts.slice(1).map((f) => f.id);
  const proposal = row.proposal;
  const run = async (factId: string | null, body: Omit<FactMutation, "expected_revision">) => {
    if (await mutate(factId, { ...body, expected_revision: state.revision })) onDone();
  };

  return (
    <div className={styles.editor}>
      {row.diagnostics.map((d) => (
        <div key={d.index} className={styles.diagnostic}>
          <p className={styles.explanation}>
            <span className={styles.quote}>«{d.diagnostic.source_quote}»</span>{" "}
            {d.diagnostic.explanation}
          </p>
          {d.diagnostic.suggestion && (
            <Button
              variant="primary"
              size="sm"
              disabled={busy}
              onClick={() => void run(d.diagnostic.fact_id, suggestionBody(row, d))}
            >
              {t("seller:row.fix", { value: d.diagnostic.suggestion })}
            </Button>
          )}
        </div>
      ))}
      {row.question && (
        <QuestionBlock
          compact
          question={row.question}
          busy={busy}
          onAnswer={(id) => void wizard.answer(id).then(onDone)}
        />
      )}
      {proposal && (
        <ProposalEditor
          proposal={proposal}
          busy={busy}
          onResolve={(action, values) =>
            void store.resolveEnum(proposal.id, action, values).then(onDone)
          }
        />
      )}
      {row.unbound && fact && (
        <BindEditor
          fact={fact}
          position={position}
          busy={busy}
          onBind={(name) =>
            void run(fact.id, {
              action: "edit",
              characteristic_name: name,
              raw_value: fact.raw_value,
              raw_unit: fact.raw_unit,
              kind: fact.kind,
            })
          }
        />
      )}
      {!row.question && !proposal && !row.unbound && (
        <ValueEditor
          row={row}
          busy={busy}
          onSave={(value) =>
            void run(fact?.id ?? null, {
              action: "edit",
              related_ids: related,
              characteristic_name: row.name,
              ...value,
            })
          }
        />
      )}
      {fact && (
        <div className={styles.secondary}>
          <Button
            variant="ghost"
            size="sm"
            icon="check"
            disabled={busy}
            onClick={() => void run(fact.id, { action: "confirm", related_ids: related })}
          >
            {t("seller:row.confirm")}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon="trash"
            disabled={busy}
            onClick={() => void run(fact.id, { action: "delete" })}
          >
            {t("seller:row.delete")}
          </Button>
        </div>
      )}
    </div>
  );
}
