import { useEffect } from "react";
import { t } from "../i18n";

export function useDocumentTitle(title: string | undefined): void {
  useEffect(() => {
    const brand = t("common:portal.brand");
    document.title = title ? `${title} | ${brand}` : brand;
  }, [title]);
}
