import { useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { CardHeader, CardTable, cardRows, exportCard, summarize } from "../../entities/card";
import { ragApi, type Session } from "../../entities/rag";
import { useDocumentTitle } from "../../shared/hooks/use-document-title";
import { useResource } from "../../shared/hooks/use-resource";
import { getLocale, t } from "../../shared/i18n";
import { Banner } from "../../shared/ui/banner/banner";
import { Button } from "../../shared/ui/button/button";
import { LinkButton } from "../../shared/ui/button/link-button";
import { Dialog } from "../../shared/ui/dialog/dialog";
import { EmptyState } from "../../shared/ui/empty-state/empty-state";
import { Facts, type Fact } from "../../shared/ui/facts/facts";
import { Illustration } from "../../shared/ui/illustration/illustration";
import { PathLinks } from "../../shared/ui/path/path-links";
import { Section } from "../../shared/ui/section/section";
import { SkeletonRows } from "../../shared/ui/skeleton/skeleton";
import { StatusBadge } from "../../shared/ui/status-badge/status-badge";
import styles from "./card-page.module.css";

function summaryFacts(session: Session): Fact[] {
  const format = (n: number) => new Intl.NumberFormat(getLocale()).format(n);
  const summary = summarize(session);
  const items: Fact[] = [
    { key: "groups", label: t("seller:card.groups"), value: format(summary.groups) },
    { key: "questions", label: t("seller:card.questions"), value: format(summary.questions) },
    {
      key: "automatic",
      label: t("seller:card.automatic"),
      value: t("seller:card.automaticValue", { count: summary.automatic, total: summary.total }),
    },
    { key: "fixes", label: t("seller:card.fixes"), value: format(summary.fixes) },
    { key: "original", label: t("seller:card.original"), value: session.description, wide: true },
  ];
  if (session.corrected && session.corrected !== session.description)
    items.push({
      key: "corrected",
      label: t("seller:final.corrected"),
      value: session.corrected,
      wide: true,
    });
  return items;
}

function Created({ session }: { readonly session: Session }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(
    Boolean((location.state as { created?: boolean } | null)?.created),
  );
  const close = () => {
    setOpen(false);
    navigate(location.pathname, { replace: true, state: null });
  };
  return (
    <Dialog
      open={open}
      size="sm"
      media={<Illustration name="target" size="lg" />}
      title={t("seller:final.createdTitle")}
      onClose={close}
      actions={
        <>
          <Button icon="download" onClick={() => exportCard(session)}>
            {t("seller:card.download")}
          </Button>
          <Button variant="primary" onClick={close}>
            {t("seller:final.toCard")}
          </Button>
        </>
      }
    >
      <p className={styles.createdText}>{t("seller:final.createdText")}</p>
    </Dialog>
  );
}

function FinalCard({ session }: { readonly session: Session }) {
  const navigate = useNavigate();
  const position = session.position;
  if (!position || session.stage !== "done")
    return (
      <Banner
        tone="warning"
        title={t("seller:final.notDone")}
        actions={
          <Button size="sm" onClick={() => navigate(`/sell?s=${session.id}`)}>
            {t("seller:final.toWizard")}
          </Button>
        }
      >
        {t("seller:final.notDoneText")}
      </Banner>
    );
  return (
    <article className={styles.card} aria-labelledby="card-title">
      <header className={styles.head}>
        <div className={styles.intro}>
          <StatusBadge tone="success" label={t("seller:final.status")} />
          <h1 id="card-title" className={styles.title}>
            {position.name}
          </h1>
          <p className={styles.lead}>{t("seller:final.lead")}</p>
        </div>
        <div className={styles.actions}>
          <Button variant="ghost" icon="download" onClick={() => exportCard(session)}>
            {t("seller:card.download")}
          </Button>
          <Button icon="edit" onClick={() => navigate(`/sell?s=${session.id}`)}>
            {t("seller:final.edit")}
          </Button>
          <Button variant="primary" icon="plus" onClick={() => navigate("/sell")}>
            {t("common:actions.restart")}
          </Button>
        </div>
      </header>
      <CardHeader position={position} withName={false} />
      <Section title={t("seller:final.values")}>
        <CardTable caption={t("seller:final.values")} rows={cardRows(session)} sources />
      </Section>
      <Section title={t("seller:card.summaryTitle")} lead={t("seller:card.summaryLead")}>
        <Facts items={summaryFacts(session)} />
      </Section>
      <Created session={session} />
    </article>
  );
}

export function CardPage() {
  const { id = "" } = useParams();
  const card = useResource(() => ragApi.session(id), `card:${id}`);
  useDocumentTitle(card.data?.position?.name ?? t("seller:final.title"));
  return (
    <div className={styles.page}>
      <PathLinks
        label={t("store:path.label")}
        items={[
          { label: t("store:path.home"), to: "/" },
          { label: t("common:nav.sell"), to: `/sell?s=${id}` },
          { label: card.data?.position?.name ?? t("seller:final.title") },
        ]}
      />
      {card.error ? (
        <EmptyState
          illustration="laptop"
          title={t("seller:final.error")}
          actions={
            <LinkButton to="/sell" variant="primary">
              {t("common:actions.restart")}
            </LinkButton>
          }
        >
          {t("errors:rag.notFound")}
        </EmptyState>
      ) : card.data ? (
        <FinalCard session={card.data} />
      ) : (
        <SkeletonRows label={t("seller:final.loading")} />
      )}
    </div>
  );
}
