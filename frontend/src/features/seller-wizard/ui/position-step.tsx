import type { Candidate, Session } from "../../../entities/rag";
import { t } from "../../../shared/i18n";
import { Collapse } from "../../../shared/motion";
import { Banner } from "../../../shared/ui/banner/banner";
import { Button } from "../../../shared/ui/button/button";
import { Disclosure } from "../../../shared/ui/disclosure/disclosure";
import { EmptyState } from "../../../shared/ui/empty-state/empty-state";
import { Facts } from "../../../shared/ui/facts/facts";
import { Section } from "../../../shared/ui/section/section";
import { StatusBadge } from "../../../shared/ui/status-badge/status-badge";
import { Table, type Column } from "../../../shared/ui/table/table";
import { OPERATION_LABEL, type RagWizard } from "../model/use-rag-wizard";
import { Differences } from "./differences";
import { GroupList } from "./group-list";
import styles from "./position-step.module.css";
import { QuestionBlock } from "./question-block";
import { StepLayout } from "./step-layout";

const columns = (
  session: Session,
  busy: boolean,
  onPick: (code: string) => void,
): readonly Column<Candidate>[] => [
  {
    key: "code",
    label: t("seller:position.code"),
    width: "minmax(180px, 220px)",
    render: (c) => <span className={styles.code}>{c.code}</span>,
  },
  { key: "name", label: t("seller:position.name"), render: (c) => c.name },
  {
    key: "differences",
    label: t("seller:position.differences"),
    width: "minmax(0, 1.4fr)",
    render: (c) =>
      Object.keys(c.differences).length ? (
        <Differences differences={c.differences} />
      ) : (
        <span className={styles.muted}>{t("seller:position.noDifferences")}</span>
      ),
  },
  {
    key: "action",
    label: "",
    width: "minmax(120px, auto)",
    align: "end",
    render: (c) =>
      session.stage === "pick" ? (
        <Button size="sm" variant="secondary" disabled={busy} onClick={() => onPick(c.code)}>
          {t("seller:position.choose")}
        </Button>
      ) : session.position?.code === c.code ? (
        <StatusBadge tone="success" label={t("seller:position.chosen")} />
      ) : (
        <StatusBadge tone="info" label={t("seller:position.fits")} />
      ),
  },
];

function SessionSummary({ session }: { readonly session: Session }) {
  const group = session.groups.find((g) => g.code === session.group);
  return (
    <Facts
      items={[
        {
          key: "group",
          label: t("seller:position.groupLabel"),
          value: group?.name ?? session.position?.name ?? session.group,
        },
        { key: "code", label: t("seller:position.groupCode"), value: session.group },
        {
          key: "left",
          label: t("seller:position.leftLabel"),
          value: t("seller:position.left", { count: session.candidates.length || 1 }),
        },
      ]}
    />
  );
}

function SessionView({
  wizard,
  session,
}: {
  readonly wizard: RagWizard;
  readonly session: Session;
}) {
  const resolved = session.stage === "spec" || session.stage === "done";
  const others = session.groups.filter((g) => g.code !== session.group);
  return (
    <>
      <SessionSummary session={session} />
      <Collapse open={Boolean(session.selection_reason)}>
        <Banner tone="info" title={t("seller:position.autoSelected")}>
          {session.selection_reason}
        </Banner>
      </Collapse>
      <Collapse open={resolved && Boolean(session.position)}>
        {session.position && (
          <Banner
            tone="success"
            title={t("seller:position.resolved", { code: session.position.code })}
          >
            {session.position.name}
          </Banner>
        )}
      </Collapse>
      <Collapse open={session.stage === "failed"}>
        <Banner
          tone="error"
          title={t("seller:position.failed")}
          actions={
            <Button size="sm" onClick={wizard.toGroups}>
              {t("seller:position.toGroups")}
            </Button>
          }
        >
          {session.message ?? t("seller:position.failedText")}
        </Banner>
      </Collapse>
      <Collapse open={session.stage === "pick"}>
        <Banner tone="warning" title={t("seller:position.pickTitle")}>
          {session.message ?? t("seller:position.pickText")}
        </Banner>
      </Collapse>
      {session.stage === "clarify" && session.question && (
        <QuestionBlock
          key={session.question.name}
          question={session.question}
          busy={wizard.busy}
          onOption={(option) => wizard.answer({ option })}
          onText={(text) => wizard.answer({ text })}
        />
      )}
      {session.candidates.length > 0 && (
        <Section title={t("seller:position.candidates")}>
          <Table
            caption={t("seller:position.candidates")}
            columns={columns(session, wizard.busy, wizard.pick)}
            rows={session.candidates}
            rowKey={(c) => c.code}
            rowTone={(c) => (session.position?.code === c.code ? "success" : "default")}
            appear
          />
        </Section>
      )}
      {others.length > 0 && (
        <Disclosure summary={t("seller:position.otherGroups", { count: others.length })}>
          <ul className={styles.others}>
            {others.map((g) => (
              <li key={g.code} className={styles.other}>
                <span className={styles.otherName}>{g.name}</span>
                <span className={styles.muted}>{g.reason}</span>
                <span className={styles.code}>{g.code}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={wizard.busy}
                  onClick={() => wizard.switchGroup(g.code)}
                >
                  {t("seller:position.switch")}
                </Button>
              </li>
            ))}
          </ul>
        </Disclosure>
      )}
    </>
  );
}

export function PositionStep({ wizard }: { readonly wizard: RagWizard }) {
  const { search, session, operation, busy } = wizard;
  const resolved = session?.stage === "spec" || session?.stage === "done";
  const auto = !session && search?.stage === "ranked" ? search.auto_select_code : null;
  const autoName = auto ? search?.candidates.find((c) => c.code === auto)?.name : null;
  return (
    <StepLayout
      id="position"
      heading={t("seller:position.heading")}
      lead={
        session
          ? t("seller:position.leadSession")
          : search?.stage === "ranked"
            ? t("seller:position.leadRanked")
            : t("seller:position.leadSearch")
      }
      busy={busy}
      status={operation ? t(OPERATION_LABEL[operation]) : undefined}
      back={
        session && search ? (
          <Button icon="chevron-left" disabled={busy} onClick={wizard.toGroups}>
            {t("seller:position.toGroups")}
          </Button>
        ) : (
          <Button icon="chevron-left" disabled={busy} onClick={() => wizard.goTo(0)}>
            {t("common:actions.back")}
          </Button>
        )
      }
      next={
        <Button
          variant="primary"
          iconEnd="chevron-right"
          disabled={!resolved || busy}
          onClick={() => wizard.goTo(2)}
        >
          {t("seller:position.toCharacteristics")}
        </Button>
      }
    >
      <Collapse open={Boolean(auto)}>
        <Banner
          tone="success"
          title={t("seller:position.autoTitle", { name: autoName ?? "" })}
          live
        >
          {search?.auto_select_reason}
        </Banner>
      </Collapse>
      {!session && !search && busy && (
        <EmptyState illustration="robot" title={t("seller:busy.searching")}>
          {t("seller:position.searchingText")}
        </EmptyState>
      )}
      {session ? (
        <SessionView wizard={wizard} session={session} />
      ) : (
        search && (
          <GroupList
            search={search}
            busy={busy}
            ranking={operation === "ranking"}
            onChoose={(code) => wizard.choose(code)}
          />
        )
      )}
    </StepLayout>
  );
}
