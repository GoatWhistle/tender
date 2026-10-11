import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CardHeader, CardTable, cardRows } from "../../../entities/card";
import { t } from "../../../shared/i18n";
import { Banner } from "../../../shared/ui/banner/banner";
import { Button } from "../../../shared/ui/button/button";
import { Dialog } from "../../../shared/ui/dialog/dialog";
import { OPERATION_LABEL, type RagWizard } from "../model/use-rag-wizard";
import { StepLayout } from "./step-layout";

export function CardStep({ wizard }: { readonly wizard: RagWizard }) {
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const { session, operation, busy } = wizard;
  if (!session?.position) return null;
  const position = session.position;
  const rows = cardRows(session);
  const complete = session.missing.length === 0;
  const done = session.stage === "done";
  const saving = operation === "saving";
  const open = (id: string, created = false) => navigate(`/cards/${id}`, { state: { created } });

  return (
    <StepLayout
      id="card"
      heading={t("seller:card.heading")}
      lead={t(done ? "seller:card.leadDone" : "seller:card.lead")}
      busy={busy && !confirming}
      status={operation ? t(OPERATION_LABEL[operation]) : undefined}
      back={
        <Button icon="chevron-left" disabled={busy} onClick={() => wizard.goTo(2)}>
          {t("common:actions.back")}
        </Button>
      }
      next={
        done ? (
          <Button variant="primary" iconEnd="chevron-right" onClick={() => open(session.id)}>
            {t("seller:card.open")}
          </Button>
        ) : (
          <Button
            variant="primary"
            icon="check"
            disabled={busy || !complete}
            onClick={() => setConfirming(true)}
          >
            {t("seller:card.finish")}
          </Button>
        )
      }
    >
      {done ? (
        <Banner tone="success" title={t("seller:card.done")}>
          {t("seller:card.doneText")}
        </Banner>
      ) : complete ? (
        <Banner tone="info" title={t("seller:card.ready")}>
          {t("seller:card.readyText")}
        </Banner>
      ) : (
        <Banner
          tone="error"
          title={t("seller:card.incomplete")}
          actions={
            <Button size="sm" onClick={() => wizard.goTo(2)}>
              {t("seller:card.toCharacteristics")}
            </Button>
          }
        >
          {session.missing.join(", ")}
        </Banner>
      )}
      <CardHeader position={position} />
      <CardTable caption={t("seller:card.values")} rows={rows} sources />
      <Dialog
        open={confirming}
        title={t("seller:card.dialogTitle")}
        onClose={() => {
          if (!saving) setConfirming(false);
        }}
        actions={
          <>
            <Button disabled={saving} onClick={() => setConfirming(false)}>
              {t("common:actions.cancel")}
            </Button>
            <Button
              variant="primary"
              pending={saving}
              disabled={busy && !saving}
              onClick={() =>
                wizard.finish((id) => {
                  setConfirming(false);
                  open(id, true);
                })
              }
            >
              {t("seller:card.confirm")}
            </Button>
          </>
        }
      >
        <CardHeader position={position} />
        <CardTable caption={t("seller:card.values")} rows={rows} />
      </Dialog>
    </StepLayout>
  );
}
