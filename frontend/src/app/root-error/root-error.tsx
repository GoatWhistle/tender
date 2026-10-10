import { useEffect } from "react";
import { useRouteError } from "react-router-dom";
import { t } from "../../shared/i18n";
import { Banner } from "../../shared/ui/banner/banner";
import { Button } from "../../shared/ui/button/button";
import { PortalShell } from "../portal-shell/portal-shell";
import styles from "./root-error.module.css";

function Message() {
  const error = useRouteError();
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <div className={styles.page}>
      <Banner
        tone="error"
        title={t("errors:boundary.title")}
        actions={
          <Button variant="primary" onClick={() => window.location.reload()}>
            {t("errors:boundary.retry")}
          </Button>
        }
      >
        {t("errors:boundary.text")}
      </Banner>
    </div>
  );
}

export function RootError() {
  return (
    <PortalShell>
      <Message />
    </PortalShell>
  );
}
