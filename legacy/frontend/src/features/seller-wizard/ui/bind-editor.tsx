import { useState } from "react";
import type { Fact } from "../../../api/types";
import type { PositionDetail } from "../../../entities/position";
import { t } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/button/button";
import { ChoiceList } from "../../../shared/ui/choice/choice-list";
import styles from "./value-editor.module.css";

export interface BindEditorProps {
  readonly fact: Fact;
  readonly position: PositionDetail | null;
  readonly busy: boolean;
  readonly onBind: (characteristic: string) => void;
}

const numeric = (f: Fact) => f.kind === "number" || f.kind === "range" || f.kind === "interval";

export function BindEditor({ fact, position, busy, onBind }: BindEditorProps) {
  const [choice, setChoice] = useState<string[]>([]);
  const options = (position?.characteristics ?? [])
    .filter((c) => c.quantitative === numeric(fact))
    .map((c) => ({
      id: c.name,
      label: c.name,
      hint: c.values.find((v) => v.unit)?.unit ?? undefined,
    }));
  const [name] = choice;
  return (
    <div className={styles.editor}>
      <p>{t("seller:row.bindLegend")}</p>
      <ChoiceList
        legend={t("seller:row.bindLegend")}
        options={options}
        value={choice}
        disabled={busy}
        onChange={setChoice}
      />
      <Button
        variant="primary"
        size="sm"
        disabled={busy || !name}
        onClick={() => name && onBind(name)}
      >
        {t("seller:row.bind")}
      </Button>
    </div>
  );
}
