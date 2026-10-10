import { useState } from "react";
import type { EnumAction, EnumProposal } from "../../../api/types";
import { t } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/button/button";
import { ChoiceList } from "../../../shared/ui/choice/choice-list";
import styles from "./value-editor.module.css";

export interface ProposalEditorProps {
  readonly proposal: EnumProposal;
  readonly busy: boolean;
  readonly onResolve: (action: EnumAction, values?: string[]) => void;
}

function permits(proposal: EnumProposal, selection: readonly string[]) {
  return (
    selection.length > 0 &&
    proposal.selections.some(
      (rule) =>
        (rule.multiple || selection.length === 1) &&
        selection.every((v) => rule.values.includes(v)),
    )
  );
}

export function ProposalEditor({ proposal, busy, onResolve }: ProposalEditorProps) {
  const [values, setValues] = useState<string[]>(proposal.suggested);
  const multiple = proposal.selections.some((rule) => rule.multiple);
  const changed = values.join("|") !== proposal.suggested.join("|");
  const allowed = permits(proposal, values);
  return (
    <div className={styles.editor}>
      <p>{proposal.reason}</p>
      <ChoiceList
        legend={proposal.characteristic}
        options={proposal.options.map((o) => ({ id: o, label: o }))}
        value={values}
        multiple={multiple}
        disabled={busy}
        onChange={setValues}
      />
      {values.length > 0 && !allowed && <p role="alert">{t("seller:row.combination")}</p>}
      <div className={styles.inline}>
        <Button
          variant="primary"
          size="sm"
          disabled={busy || !allowed}
          onClick={() => onResolve(changed ? "choose" : "accept", changed ? values : undefined)}
        >
          {t(changed ? "seller:row.save" : "seller:row.accept")}
        </Button>
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => onResolve("unknown")}>
          {t("seller:row.unknown")}
        </Button>
      </div>
    </div>
  );
}
