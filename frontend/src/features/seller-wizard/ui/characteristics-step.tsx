import { useState, type FormEvent } from "react";
import type { Doubt, Origin } from "../../../entities/rag";
import { getLocale, t, type MessageKey } from "../../../shared/i18n";
import { Collapse } from "../../../shared/motion";
import { Button } from "../../../shared/ui/button/button";
import { Disclosure } from "../../../shared/ui/disclosure/disclosure";
import { TextField } from "../../../shared/ui/field/text-field";
import { Progress } from "../../../shared/ui/progress/progress";
import { Section } from "../../../shared/ui/section/section";
import { StatusBadge, type BadgeTone } from "../../../shared/ui/status-badge/status-badge";
import { Table, type CellTone, type Column } from "../../../shared/ui/table/table";
import { buildRows, completeness, needsAction, valueText, type Row } from "../../../entities/card";
import { OPERATION_LABEL, type RagWizard } from "../model/use-rag-wizard";
import { CharacteristicEditor } from "./characteristic-editor";
import styles from "./characteristics-step.module.css";
import { ExtrasPanel } from "./extras-panel";
import { StepLayout } from "./step-layout";

const ORIGIN: Record<Origin, MessageKey> = {
  description: "seller:origin.description",
  assistant: "seller:origin.assistant",
  manual: "seller:origin.manual",
};

const DOUBT: Record<Doubt, MessageKey> = {
  large: "seller:doubt.large",
  small: "seller:doubt.small",
  negative: "seller:doubt.negative",
};

function status(row: Row): { tone: BadgeTone; label: string } {
  if (row.status === "missing") return { tone: "error", label: t("seller:status.missing") };
  if (row.status === "doubt") return { tone: "warning", label: t("seller:status.doubt") };
  if (row.status === "fixed") return { tone: "success", label: t("seller:status.fixed") };
  if (row.status === "empty") return { tone: "neutral", label: t("seller:status.empty") };
  return { tone: "info", label: t(row.origin ? ORIGIN[row.origin] : "seller:status.filled") };
}

function tone(row: Row): CellTone {
  if (row.status === "missing") return "error";
  if (row.status === "doubt") return "warning";
  if (row.status === "empty") return "muted";
  return "default";
}

function columns(onToggle: (row: Row) => void, active: string | null): Column<Row>[] {
  const format = (n: number) => new Intl.NumberFormat(getLocale()).format(n);
  return [
    {
      key: "name",
      label: t("seller:characteristics.name"),
      width: "minmax(0, 1.4fr)",
      render: (r) => (
        <span className={styles.nameCell}>
          {r.name}
          {r.required && !r.fixed && (
            <span className={styles.required}>{t("seller:characteristics.required")}</span>
          )}
        </span>
      ),
    },
    {
      key: "value",
      label: t("seller:characteristics.value"),
      width: "minmax(0, 1.3fr)",
      tone,
      render: (r) => (
        <span className={styles.valueCell}>
          <span className={styles.value}>{valueText(r, format) || t("common:noValue")}</span>
          {r.warning && <span className={styles.doubt}>{t(DOUBT[r.warning])}</span>}
        </span>
      ),
    },
    {
      key: "unit",
      label: t("seller:characteristics.unit"),
      width: "minmax(0, 0.5fr)",
      render: (r) => r.unit ?? "",
    },
    {
      key: "state",
      label: t("seller:characteristics.state"),
      width: "minmax(150px, 0.7fr)",
      render: (r) => <StatusBadge {...status(r)} />,
    },
    {
      key: "action",
      label: "",
      width: "minmax(120px, auto)",
      align: "end",
      render: (r) =>
        r.fixed ? null : (
          <Button
            variant="ghost"
            size="sm"
            aria-expanded={active === r.key}
            onClick={() => onToggle(r)}
          >
            {t(
              active === r.key
                ? "seller:row.collapse"
                : r.status === "missing" || r.status === "empty"
                  ? "seller:row.specify"
                  : "seller:row.edit",
            )}
          </Button>
        ),
    },
  ];
}

function MessageBox({ wizard }: { readonly wizard: RagWizard }) {
  const [text, setText] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim()) wizard.message(text.trim(), () => setText(""));
  };
  const reply = [...(wizard.session?.messages ?? [])].reverse().find((m) => m.role !== "user");
  return (
    <Section
      title={t("seller:characteristics.messageLabel")}
      lead={t("seller:characteristics.messageLead")}
    >
      <form className={styles.message} onSubmit={submit}>
        <TextField
          hideLabel
          label={t("seller:characteristics.messageLabel")}
          placeholder={t("seller:characteristics.messagePlaceholder")}
          value={text}
          disabled={wizard.busy}
          onChange={(e) => setText(e.target.value)}
        />
        <Button type="submit" variant="secondary" disabled={wizard.busy || !text.trim()}>
          {t("seller:editor.apply")}
        </Button>
        {reply && <p className={styles.reply}>{reply.text}</p>}
      </form>
    </Section>
  );
}

export function CharacteristicsStep({ wizard }: { readonly wizard: RagWizard }) {
  const { session, operation, busy } = wizard;
  const [open, setOpen] = useState<string | null>(null);
  if (!session) return null;
  const rows = buildRows(session);
  const active = open ?? rows.find(needsAction)?.key ?? null;
  const { done, total } = completeness(rows);
  const toggle = (row: Row) => setOpen(active === row.key ? "" : row.key);
  const main = rows.filter((r) => r.status !== "empty");
  const optional = rows.filter((r) => r.status === "empty");
  const table = (items: Row[], caption: string) => (
    <Table
      caption={caption}
      columns={columns(toggle, active)}
      rows={items}
      rowKey={(r) => r.key}
      rowTone={(r) => (r.status === "missing" ? "error" : "default")}
      expanded={(r) => (
        <Collapse open={r.key === active} className={styles.extra} role="row">
          <div role="cell">
            <CharacteristicEditor row={r} wizard={wizard} />
          </div>
        </Collapse>
      )}
    />
  );

  return (
    <StepLayout
      id="characteristics"
      heading={t("seller:characteristics.heading")}
      lead={
        session.position
          ? t("seller:characteristics.leadPosition", {
              name: session.position.name,
              code: session.position.code,
            })
          : t("seller:characteristics.lead")
      }
      busy={busy}
      status={operation ? t(OPERATION_LABEL[operation]) : undefined}
      aside={
        total > 0 && (
          <div className={styles.progress}>
            <Progress
              value={done}
              max={total}
              label={t("seller:characteristics.progressLabel")}
              caption={t("seller:characteristics.progress", { done, total })}
            />
          </div>
        )
      }
      back={
        <Button icon="chevron-left" disabled={busy} onClick={() => wizard.goTo(1)}>
          {t("common:actions.back")}
        </Button>
      }
      next={
        <Button
          variant="primary"
          iconEnd="chevron-right"
          disabled={busy}
          onClick={() => wizard.goTo(3)}
        >
          {t("seller:characteristics.toCard")}
        </Button>
      }
    >
      <div className={styles.tables}>
        {table(main, t("seller:characteristics.caption"))}
        {optional.length > 0 && (
          <Disclosure
            summary={t("seller:characteristics.optional", { count: optional.length })}
            defaultOpen={main.length === 0}
          >
            {table(optional, t("seller:characteristics.optionalCaption"))}
          </Disclosure>
        )}
      </div>
      <MessageBox wizard={wizard} />
      {session.extras_allowed && <ExtrasPanel wizard={wizard} session={session} />}
    </StepLayout>
  );
}
