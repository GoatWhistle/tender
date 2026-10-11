import { useDocumentTitle } from "../../../shared/hooks/use-document-title";
import { t, type MessageKey } from "../../../shared/i18n";
import { Collapse, useLoadingIndicator } from "../../../shared/motion";
import { Banner } from "../../../shared/ui/banner/banner";
import { Button } from "../../../shared/ui/button/button";
import { Stepper } from "../../../shared/ui/stepper/stepper";
import { useRagWizard } from "../model/use-rag-wizard";
import { CardStep } from "./card-step";
import { CharacteristicsStep } from "./characteristics-step";
import { DescribeStep } from "./describe-step";
import { PositionStep } from "./position-step";
import styles from "./wizard.module.css";

const STEPS = ["describe", "position", "characteristics", "card"] as const;

const STEP_LABEL: Record<(typeof STEPS)[number], MessageKey> = {
  describe: "seller:steps.describe",
  position: "seller:steps.position",
  characteristics: "seller:steps.characteristics",
  card: "seller:steps.card",
};

export function SellerWizard() {
  const wizard = useRagWizard();
  useDocumentTitle(t("seller:title"));
  const { step, reachable, goTo, failure, busy } = wizard;
  const steps = STEPS.map((id) => ({ id, label: t(STEP_LABEL[id]) }));
  const id = STEPS[step] ?? "describe";
  const stale = useLoadingIndicator(busy, "--delay-skeleton");

  return (
    <div className={styles.page}>
      <div className={styles.top}>
        <h1 className={styles.title}>{t("seller:title")}</h1>
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
      <Collapse open={Boolean(failure)}>
        {failure && (
          <Banner
            tone="error"
            title={failure.title}
            live
            actions={
              <Button size="sm" icon="history" disabled={busy} onClick={wizard.retry}>
                {t("common:actions.retry")}
              </Button>
            }
          >
            {failure.text}
          </Banner>
        )}
      </Collapse>
      <section
        key={id}
        className={styles.panel}
        aria-labelledby={`step-${id}`}
        aria-busy={busy}
        data-stale={stale && id !== "position" ? true : undefined}
      >
        {id === "describe" && <DescribeStep wizard={wizard} />}
        {id === "position" && <PositionStep wizard={wizard} />}
        {id === "characteristics" && <CharacteristicsStep wizard={wizard} />}
        {id === "card" && <CardStep wizard={wizard} />}
      </section>
    </div>
  );
}
