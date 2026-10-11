import { useDocumentTitle } from "../../shared/hooks/use-document-title";
import { t } from "../../shared/i18n";
import { LinkButton } from "../../shared/ui/button/link-button";
import { EmptyState } from "../../shared/ui/empty-state/empty-state";
import styles from "./not-found-page.module.css";

export function NotFoundPage() {
  useDocumentTitle(t("common:notFound.title"));
  return (
    <div className={styles.page}>
      <EmptyState
        illustration="laptop"
        heading="h1"
        title={t("common:notFound.title")}
        actions={
          <LinkButton to="/" variant="primary">
            {t("common:notFound.home")}
          </LinkButton>
        }
      >
        {t("common:notFound.text")}
      </EmptyState>
    </div>
  );
}
