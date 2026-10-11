import { t, type MessageKey } from "../../shared/i18n";
import { StatusBadge, type BadgeTone } from "../../shared/ui/status-badge/status-badge";
import { Table, type Column } from "../../shared/ui/table/table";
import type { CardRow, CardSource } from "./card";

const SOURCE: Record<CardSource, { readonly tone: BadgeTone; readonly label: MessageKey }> = {
  fixed: { tone: "success", label: "seller:card.fromPosition" },
  filled: { tone: "info", label: "seller:card.filled" },
  extra: { tone: "neutral", label: "seller:card.extra" },
  missing: { tone: "error", label: "seller:status.missing" },
};

export interface CardTableProps {
  readonly caption: string;
  readonly rows: readonly CardRow[];
  readonly sources?: boolean;
}

export function CardTable({ caption, rows, sources = false }: CardTableProps) {
  const columns: Column<CardRow>[] = [
    { key: "name", label: t("seller:characteristics.name"), render: (r) => r.name },
    {
      key: "value",
      label: t("seller:characteristics.value"),
      render: (r) => r.value || t("common:noValue"),
      tone: (r) => (r.source === "missing" ? "error" : "default"),
    },
    {
      key: "unit",
      label: t("seller:characteristics.unit"),
      width: "minmax(0, 0.5fr)",
      render: (r) => r.unit,
    },
  ];
  if (sources)
    columns.push({
      key: "source",
      label: t("seller:card.source"),
      width: "minmax(150px, 0.6fr)",
      render: (r) => <StatusBadge tone={SOURCE[r.source].tone} label={t(SOURCE[r.source].label)} />,
    });
  return <Table caption={caption} columns={columns} rows={rows} rowKey={(r) => r.key} />;
}
