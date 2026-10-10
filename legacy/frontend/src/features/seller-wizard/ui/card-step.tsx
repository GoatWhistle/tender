import { usePosition } from "../../../entities/position";
import { t } from "../../../shared/i18n";
import { Banner } from "../../../shared/ui/banner/banner";
import { Button } from "../../../shared/ui/button/button";
import { CatalogPath } from "../../../shared/ui/path/catalog-path";
import { Table, type Column } from "../../../shared/ui/table/table";
import { buildRows, completeness, factText, type CharacteristicRow } from "../model/rows";
import { chosenPositionCode, compatibleCandidates } from "../model/steps";
import type { Wizard } from "../model/use-wizard";
import styles from "./card-step.module.css";
import { StepLayout } from "./step-layout";

const columns = (): readonly Column<CharacteristicRow>[] => [
  { key: "name", label: t("seller:characteristics.name"), render: (r) => r.name },
  {
    key: "value",
    label: t("seller:characteristics.value"),
    render: (r) => r.facts.map(factText).join("; ") || t("common:noValue"),
    tone: (r) => (r.facts.length ? "default" : r.required ? "error" : "muted"),
  },
  {
    key: "unit",
    label: t("seller:characteristics.unit"),
    width: "minmax(0, 0.5fr)",
    render: (r) => r.unit ?? "",
  },
];

export function CardStep({ wizard }: { readonly wizard: Wizard }) {
  const { view, goTo, restart } = wizard;
  const state = view.state;
  const position = usePosition(chosenPositionCode(state));
  if (!state?.path) return null;
  const chosen = compatibleCandidates(state)[0];
  const rows = buildRows(state, position.data).filter((r) => r.facts.length > 0 || r.required);
  const { done, total } = completeness(rows);
  const complete = state.card_complete || (total > 0 && done === total);

  return (
    <StepLayout
      id="card"
      heading={t("seller:card.heading")}
      busy={view.busy}
      back={
        <Button icon="chevron-left" onClick={() => goTo(2)}>
          {t("common:actions.back")}
        </Button>
      }
      next={
        <Button variant="primary" icon="plus" onClick={restart}>
          {t("common:actions.restart")}
        </Button>
      }
    >
      <dl className={styles.facts}>
        <dt>{t("seller:card.name")}</dt>
        <dd className={styles.name}>{chosen?.name ?? state.path.group.name}</dd>
        <dt>{t("seller:card.category")}</dt>
        <dd>
          <CatalogPath
            items={[state.path.category, state.path.group.name]}
            label={t("seller:card.category")}
          />
        </dd>
        <dt>{t("seller:card.code")}</dt>
        <dd className={styles.code}>{chosen?.code ?? state.path.group.code}</dd>
        {position.data && (
          <>
            <dt>{t("seller:card.okpd2")}</dt>
            <dd>
              {position.data.okpd2} {position.data.okpd2_name}
            </dd>
          </>
        )}
        <dt>{t("seller:card.description")}</dt>
        <dd className={styles.description}>{state.messages.map((m) => m.text).join("\n")}</dd>
      </dl>
      {complete ? (
        <Banner tone="success" title={t("seller:card.complete")}>
          {t("seller:card.completeText")}
        </Banner>
      ) : (
        <Banner
          tone="warning"
          title={t("seller:card.incomplete")}
          actions={
            <Button size="sm" onClick={() => goTo(2)}>
              {t("seller:card.toCharacteristics")}
            </Button>
          }
        >
          {t("seller:card.incompleteText")}
        </Banner>
      )}
      <Table
        caption={t("seller:card.values")}
        columns={columns()}
        rows={rows}
        rowKey={(r) => r.key}
      />
    </StepLayout>
  );
}
