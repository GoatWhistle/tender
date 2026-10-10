import { useState } from "react";
import { usePosition } from "../../../entities/position";
import { t } from "../../../shared/i18n";
import { Collapse } from "../../../shared/motion";
import { Banner } from "../../../shared/ui/banner/banner";
import { Button } from "../../../shared/ui/button/button";
import { Disclosure } from "../../../shared/ui/disclosure/disclosure";
import { Progress } from "../../../shared/ui/progress/progress";
import { SkeletonRows } from "../../../shared/ui/skeleton/skeleton";
import { Table } from "../../../shared/ui/table/table";
import { buildRows, completeness, unboundDiagnostics, type CharacteristicRow } from "../model/rows";
import { chosenPositionCode } from "../model/steps";
import type { Wizard } from "../model/use-wizard";
import styles from "./characteristics-step.module.css";
import { columns, needsAction } from "./row-cells";
import { RowEditor } from "./row-editor";
import { StepLayout } from "./step-layout";

export function CharacteristicsStep({ wizard }: { readonly wizard: Wizard }) {
  const { view, goTo, reachable } = wizard;
  const state = view.state;
  const position = usePosition(chosenPositionCode(state));
  const [open, setOpen] = useState<string | null>(null);
  if (!state) return null;

  const rows = buildRows(state, position.data);
  const firstAction = rows.find(needsAction)?.key ?? null;
  const active = open === null ? firstAction : open;
  const { done, total } = completeness(rows);
  const notes = unboundDiagnostics(state, rows);
  const analysisNotes = state.errors.flatMap((e) => ("code" in e ? [e.message] : []));
  const toggle = (row: CharacteristicRow) => setOpen(active === row.key ? "" : row.key);
  const main = rows.filter((r) => r.status !== "empty");
  const optional = rows.filter((r) => r.status === "empty");
  const table = (items: CharacteristicRow[], caption: string) => (
    <Table
      caption={caption}
      columns={columns(toggle, active)}
      rows={items}
      rowKey={(r) => r.key}
      rowTone={(r) => (r.status === "error" ? "error" : "default")}
      expanded={(r) => (
        <Collapse open={r.key === active} className={styles.extra} role="row">
          <div role="cell">
            <RowEditor
              row={r}
              wizard={wizard}
              position={position.data}
              onDone={() => setOpen("")}
            />
          </div>
        </Collapse>
      )}
    />
  );

  return (
    <StepLayout
      id="characteristics"
      heading={t("seller:characteristics.heading")}
      lead={t("seller:characteristics.lead")}
      busy={view.busy}
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
        <Button icon="chevron-left" onClick={() => goTo(1)}>
          {t("common:actions.back")}
        </Button>
      }
      next={
        <Button
          variant="primary"
          iconEnd="chevron-right"
          disabled={reachable < 3}
          onClick={() => goTo(3)}
        >
          {t("common:actions.next")}
        </Button>
      }
    >
      <Collapse open={notes.length > 0}>
        <Banner tone="warning" title={t("seller:characteristics.notes")}>
          {notes.map(({ diagnostic: d, index }) => (
            <p key={index}>
              «{d.source_quote}»: {d.explanation}
            </p>
          ))}
        </Banner>
      </Collapse>
      <Collapse open={position.failed}>
        <Banner tone="error" title={t("errors:position")} />
      </Collapse>
      {analysisNotes.length > 0 && (
        <p className={styles.notes}>
          {t("seller:characteristics.analysisNotes")}: {analysisNotes.join(" ")}
        </p>
      )}
      {!position.data && !position.failed ? (
        <SkeletonRows label={t("seller:characteristics.loading")} />
      ) : (
        <>
          {table(main, t("seller:characteristics.caption"))}
          {optional.length > 0 && (
            <Disclosure
              summary={t("seller:characteristics.optional", { count: optional.length })}
              defaultOpen={main.length === 0}
            >
              {table(optional, t("seller:characteristics.optionalCaption"))}
            </Disclosure>
          )}
        </>
      )}
    </StepLayout>
  );
}
