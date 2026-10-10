import { t, type MessageKey } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/button/button";
import { StatusBadge, type BadgeTone } from "../../../shared/ui/status-badge/status-badge";
import type { CellTone, Column } from "../../../shared/ui/table/table";
import { factText, type CharacteristicRow, type RowStatus } from "../model/rows";
import styles from "./characteristics-step.module.css";

const STATUS: Record<RowStatus, { label: MessageKey; tone: BadgeTone }> = {
  error: { label: "seller:status.error", tone: "error" },
  question: { label: "seller:status.question", tone: "warning" },
  proposal: { label: "seller:status.proposal", tone: "warning" },
  ambiguous: { label: "seller:status.ambiguous", tone: "warning" },
  missing: { label: "seller:status.missing", tone: "error" },
  filled: { label: "seller:status.filled", tone: "info" },
  confirmed: { label: "seller:status.confirmed", tone: "success" },
  catalog: { label: "seller:status.catalog", tone: "success" },
  empty: { label: "seller:status.empty", tone: "neutral" },
};

const ACTION: Record<RowStatus, MessageKey> = {
  error: "seller:row.edit",
  question: "seller:row.specify",
  proposal: "seller:row.accept",
  ambiguous: "seller:row.edit",
  missing: "seller:row.specify",
  filled: "seller:row.edit",
  confirmed: "seller:row.edit",
  catalog: "seller:row.edit",
  empty: "seller:row.specify",
};

export const needsAction = (r: CharacteristicRow) =>
  ["error", "question", "proposal", "ambiguous", "missing"].includes(r.status);

export function toneOf(r: CharacteristicRow): CellTone {
  if (r.status === "error") return "error";
  if (r.status === "proposal") return "warning";
  if (r.facts.length === 0 && !r.proposal) return "muted";
  return "default";
}

function Value({ row }: { readonly row: CharacteristicRow }) {
  if (row.facts.length > 0)
    return <span className={styles.value}>{row.facts.map(factText).join("; ")}</span>;
  if (row.proposal)
    return <span>{t("seller:row.suggested", { value: row.proposal.suggested.join(", ") })}</span>;
  return <span>{t("common:noValue")}</span>;
}

export function columns(
  onToggle: (row: CharacteristicRow) => void,
  active: string | null,
): Column<CharacteristicRow>[] {
  return [
    {
      key: "name",
      label: t("seller:characteristics.name"),
      width: "minmax(0, 1.4fr)",
      render: (r) => (
        <span className={styles.nameCell}>
          {r.unbound ? `«${r.name}»` : r.name}
          {r.unbound && <span className={styles.unbound}>{t("seller:row.unbound")}</span>}
          {r.required && (
            <span className={styles.required}>{t("seller:characteristics.required")}</span>
          )}
        </span>
      ),
    },
    {
      key: "value",
      label: t("seller:characteristics.value"),
      width: "minmax(0, 1.2fr)",
      render: (r) => <Value row={r} />,
      tone: toneOf,
    },
    {
      key: "unit",
      label: t("seller:characteristics.unit"),
      width: "minmax(0, 0.6fr)",
      render: (r) => r.unit ?? "",
    },
    {
      key: "state",
      label: t("seller:characteristics.state"),
      width: "minmax(130px, 0.6fr)",
      render: (r) => <StatusBadge tone={STATUS[r.status].tone} label={t(STATUS[r.status].label)} />,
    },
    {
      key: "action",
      label: "",
      width: "minmax(120px, auto)",
      align: "end",
      render: (r) => (
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={active === r.key}
          onClick={() => onToggle(r)}
        >
          {t(
            active === r.key
              ? "seller:row.collapse"
              : r.unbound
                ? "seller:row.bind"
                : ACTION[r.status],
          )}
        </Button>
      ),
    },
  ];
}
