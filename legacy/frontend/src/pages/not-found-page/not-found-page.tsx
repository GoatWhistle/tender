import { useDocumentTitle } from "../../shared/hooks/use-document-title";
import { t } from "../../shared/i18n";
import { Banner } from "../../shared/ui/banner/banner";
import { LinkButton } from "../../shared/ui/button/link-button";
import styles from "./not-found-page.module.css";

export function NotFoundPage() {
  useDocumentTitle(t("common:notFound.title"));
  return (
    <div className={styles.page}>
      <Banner
        tone="warning"
        title={t("common:notFound.title")}
        actions={
          <LinkButton to="/" variant="primary">
            {t("common:notFound.home")}
          </LinkButton>
        }
      >
        {t("common:notFound.text")}
      </Banner>
    </div>
  );
}
