import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { api, unwrap } from "@/shared/api/client"
import { Spinner } from "@/shared/motion/primitives"
import { Button } from "@/shared/ui/button"
import { CategoryIcon } from "@/shared/ui/category-icon/category-icon"
import { BackendText } from "@/shared/ui/message"
import styles from "./catalog-position.module.css"

export function CatalogPosition({ code }: { readonly code: string }) {
  const { t } = useTranslation("rag")
  const query = useQuery({
    queryKey: ["catalog-position", code],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/catalog/{code}", { params: { path: { code } }, signal })),
  })
  if (query.isPending)
    return (
      <div className={styles.status} role="status">
        <Spinner />
        {t("catalogLoading")}
      </div>
    )
  if (query.isError)
    return (
      <div className={styles.status} role="alert">
        <p>{t("catalogError")}</p>
        <Button onClick={() => void query.refetch()}>{t("catalogRetry")}</Button>
      </div>
    )
  const position = query.data
  return (
    <section className={styles.details} aria-label={t("catalogContents")}>
      <header>
        <CategoryIcon code={position.code} size="lg" />
        <p>{position.code}</p>
        <h2>
          <BackendText>{position.name}</BackendText>
        </h2>
      </header>
      <h3>{t("catalogContents")}</h3>
      <dl className={styles.metadata}>
        <div>
          <dt>{t("catalogOkpd")}</dt>
          <dd>
            {position.okpd2} <BackendText>{position.okpd2_name}</BackendText>
          </dd>
        </div>
        <div>
          <dt>{t("catalogUnits")}</dt>
          <dd>
            <BackendText>{position.units.join("; ") || t("emptyValue")}</BackendText>
          </dd>
        </div>
        {position.rubrics.length > 0 && (
          <div>
            <dt>{t("catalogRubrics")}</dt>
            <dd>
              <BackendText>{position.rubrics.join("; ")}</BackendText>
            </dd>
          </div>
        )}
      </dl>
      {position.characteristics.length ? (
        <dl className={styles.characteristics}>
          {position.characteristics.map((field) => (
            <div key={`${field.code}-${field.name}`}>
              <dt>
                <BackendText>{field.name}</BackendText>
                <span>
                  {t(field.required ? "required" : "optional")}
                  {" / "}
                  {t(
                    field.kind === "1"
                      ? "catalogFixed"
                      : field.kind === "3"
                        ? "catalogMultiple"
                        : "catalogSingle",
                  )}
                </span>
              </dt>
              <dd>
                {field.values.length ? (
                  <ul>
                    {[...new Set(field.values)].map((value) => (
                      <li key={value}>
                        <BackendText>{value || t("emptyValue")}</BackendText>
                      </li>
                    ))}
                  </ul>
                ) : (
                  t("emptyValue")
                )}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p>{t("catalogEmpty")}</p>
      )}
    </section>
  )
}
