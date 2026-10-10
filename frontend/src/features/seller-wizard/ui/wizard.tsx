import { useDocumentTitle } from "../../../shared/hooks/use-document-title";
import { t, type MessageKey } from "../../../shared/i18n";
import { Collapse, useLoadingIndicator } from "../../../shared/motion";
import { Button } from "../../../shared/ui/button/button";
import { Stepper } from "../../../shared/ui/stepper/stepper";
import { STEPS } from "../model/steps";
import { useWizard } from "../model/use-wizard";
import { CardStep } from "./card-step";
import { CharacteristicsStep } from "./characteristics-step";
import { DescribeStep } from "./describe-step";
import { FailureBanner } from "./failure-banner";
import { PositionStep } from "./position-step";
import styles from "./wizard.module.css";

const STEP_LABEL: Record<(typeof STEPS)[number], MessageKey> = {
  describe: "seller:steps.describe",
  position: "seller:steps.position",
  characteristics: "seller:steps.characteristics",
  card: "seller:steps.card",
};

export function SellerWizard() {
  const wizard = useWizard();
  useDocumentTitle(t("seller:title"));
  const { view, step, reachable, goTo, restart } = wizard;
  const steps = STEPS.map((id) => ({ id, label: t(STEP_LABEL[id]) }));
  const id = STEPS[step] ?? "describe";
  const stale = useLoadingIndicator(view.busy, "--delay-skeleton");

  return (
    <div className={styles.page}>
      <div className={styles.top}>
        <h1 className={styles.title}>{t("seller:title")}</h1>
        {view.sessionId && (
          <Button variant="ghost" icon="plus" onClick={restart}>
            {t("common:actions.restart")}
          </Button>
        )}
      </div>
      <div className={styles.steps}>
        <Stepper
          steps={steps}
          current={step}
          reachable={reachable}
          label={t("seller:steps.label")}
          onSelect={goTo}
        />
      </div>
      <Collapse open={Boolean(view.failure)}>
        {view.failure && <FailureBanner failure={view.failure} />}
      </Collapse>
      <section
        key={id}
        className={styles.panel}
        aria-labelledby={`step-${id}`}
        aria-busy={view.busy}
        data-stale={stale || undefined}
      >
        {id === "describe" && <DescribeStep wizard={wizard} />}
        {id === "position" && <PositionStep wizard={wizard} />}
        {id === "characteristics" && <CharacteristicsStep wizard={wizard} />}
        {id === "card" && <CardStep wizard={wizard} />}
      </section>
    </div>
  );
}
