import type { Candidate, SessionState } from "../../../api/types";
import { t } from "../../../shared/i18n";
import { Collapse } from "../../../shared/motion";
import { Button } from "../../../shared/ui/button/button";
import { Disclosure } from "../../../shared/ui/disclosure/disclosure";
import { CatalogPath } from "../../../shared/ui/path/catalog-path";
import { Progress } from "../../../shared/ui/progress/progress";
import { StatusBadge } from "../../../shared/ui/status-badge/status-badge";
import { Table, type Column } from "../../../shared/ui/table/table";
import { compatibleCandidates, isNarrowingQuestion } from "../model/steps";
import type { Wizard } from "../model/use-wizard";
import { PositionStatus } from "./position-status";
import styles from "./position-step.module.css";
import { QuestionBlock } from "./question-block";
import { StepLayout } from "./step-layout";

const columns = (): readonly Column<Candidate>[] => [
  {
    key: "code",
    label: t("seller:position.code"),
    width: "minmax(180px, 220px)",
    render: (c) => c.code,
  },
  {
    key: "name",
    label: t("seller:position.name"),
    render: (c) => (
      <span className={styles.name}>
        {c.name}
        {c.reason && <span className={styles.reason}>{c.reason.text}</span>}
      </span>
    ),
  },
  {
    key: "state",
    label: t("seller:position.state"),
    width: "minmax(120px, 160px)",
    render: (c) => (
      <StatusBadge
        tone={c.excluded ? "error" : "success"}
        label={t(c.excluded ? "seller:position.excluded" : "seller:position.fits")}
      />
    ),
  },
];

function Summary({ state }: { readonly state: SessionState }) {
  if (!state.path) return null;
  const { in_group, compatible } = state.candidate_counts;
  return (
    <dl className={styles.summary}>
      <div className={styles.pair}>
        <dt>{t("seller:position.path")}</dt>
        <dd>
          <CatalogPath
            items={[state.path.category, state.path.group.name]}
            label={t("seller:position.path")}
          />
        </dd>
      </div>
      <div className={styles.pair}>
        <dt>{t("seller:position.groupLabel")}</dt>
        <dd className={styles.code}>{state.path.group.code}</dd>
      </div>
      <div className={styles.pair}>
        <dt>{t("seller:position.narrowingLabel")}</dt>
        <dd>
          <Progress
            value={in_group - compatible}
            max={Math.max(in_group - 1, 1)}
            label={t("seller:position.narrowingLabel")}
            caption={t("seller:position.narrowing", { compatible, total: in_group })}
          />
        </dd>
      </div>
    </dl>
  );
}

export function PositionStep({ wizard }: { readonly wizard: Wizard }) {
  const { view, goTo } = wizard;
  const state = view.state;
  if (!state) return null;
  const narrowing = isNarrowingQuestion(state) ? state.next_question : null;
  const rows = [...compatibleCandidates(state), ...state.candidates.filter((c) => c.excluded)];

  return (
    <StepLayout
      id="position"
      heading={t("seller:position.heading")}
      busy={view.busy}
      back={
        <Button icon="chevron-left" onClick={() => goTo(0)}>
          {t("common:actions.back")}
        </Button>
      }
      next={
        <Button
          variant="primary"
          iconEnd="chevron-right"
          disabled={!state.path}
          onClick={() => goTo(2)}
        >
          {t("common:actions.next")}
        </Button>
      }
    >
      <Summary state={state} />
      <Collapse open={!(narrowing && state.status === "needs_clarification")}>
        <PositionStatus state={state} />
      </Collapse>
      <Collapse open={Boolean(narrowing)}>
        {narrowing && (
          <QuestionBlock
            question={narrowing}
            busy={view.busy}
            onAnswer={(id) => void wizard.answer(id)}
          />
        )}
      </Collapse>
      {rows.length > 0 && (
        <section className={styles.block} aria-labelledby="candidates-title">
          <h3 id="candidates-title" className={styles.blockTitle}>
            {t("seller:position.candidates")}
          </h3>
          <Table
            caption={t("seller:position.candidates")}
            columns={columns()}
            rows={rows}
            rowKey={(c) => c.code}
            rowTone={(c) => (c.excluded ? "muted" : "default")}
          />
        </section>
      )}
      {state.alternatives.length > 0 && (
        <Disclosure
          summary={t("seller:position.alternatives", { count: state.alternatives.length })}
        >
          <p className={styles.hint}>{t("seller:position.alternativesHint")}</p>
          <ul className={styles.alternatives}>
            {state.alternatives.map((a) => (
              <li key={a.code} className={styles.alternative}>
                <span>{a.name}</span>
                <span className={styles.muted}>{a.category}</span>
                <span className={styles.code}>{a.code}</span>
              </li>
            ))}
          </ul>
        </Disclosure>
      )}
    </StepLayout>
  );
}
