import { useId, useState, type FormEvent } from "react";
import type { FactValue } from "../../../api/types";
import { t } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/button/button";
import { ChoiceList } from "../../../shared/ui/choice/choice-list";
import { TextField } from "../../../shared/ui/field/text-field";
import { factText, type CharacteristicRow } from "../model/rows";
import styles from "./value-editor.module.css";

type Value = Pick<FactValue, "raw_value" | "raw_unit" | "kind">;

export interface ValueEditorProps {
  readonly row: CharacteristicRow;
  readonly busy: boolean;
  readonly onSave: (value: Value) => void;
}

const RANGE = /^\s*([+-]?[0-9.,]+)\s*(?:-|–|\.\.)\s*([+-]?[0-9.,]+)\s*$/;
const NUMBER = /^\s*[+-]?[0-9]+(?:[.,][0-9]+)?\s*$/;

function parse(raw: string, unit: string): Value {
  const range = raw.match(RANGE);
  if (range)
    return { raw_value: `${range[1]}..${range[2]}`, raw_unit: unit || null, kind: "range" };
  if (NUMBER.test(raw)) return { raw_value: raw.trim(), raw_unit: unit || null, kind: "number" };
  return { raw_value: raw.trim(), raw_unit: unit || null, kind: "text" };
}

export function ValueEditor({ row, busy, onSave }: ValueEditorProps) {
  const id = useId();
  const options = (row.characteristic?.values ?? [])
    .filter((v) => !row.characteristic?.quantitative && v.label)
    .map((v) => ({ id: v.label, label: v.label }));
  const current = row.facts.map(factText);
  const [choice, setChoice] = useState<string[]>(
    current.filter((v) => options.some((o) => o.id === v)),
  );
  const [raw, setRaw] = useState(current[0] ?? "");
  const [unit, setUnit] = useState(row.unit ?? "");

  if (options.length > 0) {
    return (
      <div className={styles.editor}>
        <ChoiceList
          legend={row.name}
          options={options}
          value={choice}
          multiple={row.characteristic?.multi ?? false}
          disabled={busy}
          onChange={setChoice}
        />
        <Button
          variant="primary"
          size="sm"
          disabled={busy || choice.length === 0}
          onClick={() => onSave({ raw_value: choice.join(", "), raw_unit: null, kind: "text" })}
        >
          {t("seller:row.save")}
        </Button>
      </div>
    );
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (raw.trim()) onSave(parse(raw, unit.trim()));
  };
  return (
    <form className={styles.inline} onSubmit={submit}>
      <TextField
        id={`${id}-value`}
        label={t("seller:row.value")}
        value={raw}
        autoFocus
        onChange={(e) => setRaw(e.target.value)}
      />
      <TextField
        id={`${id}-unit`}
        label={t("seller:row.unit")}
        value={unit}
        onChange={(e) => setUnit(e.target.value)}
      />
      <Button type="submit" variant="primary" disabled={busy || !raw.trim()}>
        {t("seller:row.save")}
      </Button>
    </form>
  );
}
