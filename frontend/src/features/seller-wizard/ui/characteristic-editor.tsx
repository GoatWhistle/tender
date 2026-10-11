import { useState, type FormEvent } from "react";
import type { Band } from "../../../entities/rag";
import { t } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/button/button";
import { ChoiceList } from "../../../shared/ui/choice/choice-list";
import { TextField } from "../../../shared/ui/field/text-field";
import type { RagWizard } from "../model/use-rag-wizard";
import type { Row } from "../../../entities/card";
import styles from "./characteristics-step.module.css";

const COMPACT_FROM = 8;

function bandText(b: Band): string {
  const low = b.min === null ? "" : `${b.min_inclusive ? "≥" : ">"} ${b.min}`;
  const high = b.max === null ? "" : `${b.max_inclusive ? "≤" : "<"} ${b.max}`;
  return [low, high].filter(Boolean).join(" ");
}

function NumberEditor({ row, wizard }: { readonly row: Row; readonly wizard: RagWizard }) {
  const [text, setText] = useState(row.number === null ? "" : String(row.number));
  const parsed = Number(text.replace(",", "."));
  const valid = text.trim() !== "" && Number.isFinite(parsed);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (valid) wizard.number(row.name, parsed);
  };
  return (
    <form className={styles.numberForm} onSubmit={submit}>
      <TextField
        label={t("seller:editor.number", { unit: row.unit ?? "" })}
        inputMode="decimal"
        value={text}
        disabled={wizard.busy}
        onChange={(e) => setText(e.target.value)}
      />
      <Button type="submit" variant="primary" disabled={wizard.busy || !valid}>
        {t("common:actions.save")}
      </Button>
      {row.number !== null && (
        <Button
          variant="ghost"
          disabled={wizard.busy}
          onClick={() => wizard.number(row.name, null)}
        >
          {t("seller:editor.clear")}
        </Button>
      )}
      {row.bands.length > 0 && (
        <p className={styles.bands}>
          {t("seller:editor.bands")}:{" "}
          {row.bands.map((b) => `${b.option} (${bandText(b)})`).join("; ")}
        </p>
      )}
    </form>
  );
}

function WordsEditor({ row, wizard }: { readonly row: Row; readonly wizard: RagWizard }) {
  const [text, setText] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim()) wizard.describe(text.trim(), row.name, () => setText(""));
  };
  return (
    <form className={styles.wordsForm} onSubmit={submit}>
      <TextField
        label={t("seller:editor.words")}
        placeholder={t("seller:editor.wordsPlaceholder")}
        value={text}
        disabled={wizard.busy}
        onChange={(e) => setText(e.target.value)}
      />
      <Button type="submit" variant="secondary" disabled={wizard.busy || !text.trim()}>
        {t("seller:editor.apply")}
      </Button>
    </form>
  );
}

export function CharacteristicEditor({
  row,
  wizard,
}: {
  readonly row: Row;
  readonly wizard: RagWizard;
}) {
  const numeric = row.bands.length > 0 || row.number !== null;
  return (
    <div className={styles.editor}>
      {numeric && <NumberEditor row={row} wizard={wizard} />}
      {!numeric && row.options.length > 0 && (
        <ChoiceList
          legend={t("seller:editor.options")}
          options={row.options.map((o) => ({ id: o, label: o }))}
          value={row.values}
          multiple={row.multiple}
          compact={row.options.length >= COMPACT_FROM}
          disabled={wizard.busy}
          onChange={(selected) => wizard.values(row.name, selected)}
        />
      )}
      <WordsEditor row={row} wizard={wizard} />
    </div>
  );
}
