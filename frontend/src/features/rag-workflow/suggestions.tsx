import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import type { Suggestion } from "@/entities/rag"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { api, unwrap } from "@/shared/api/client"
import { Spinner } from "@/shared/motion/primitives"
import { Button } from "@/shared/ui/button"
import { Icon } from "@/shared/ui/icon"
import { BackendText } from "@/shared/ui/message"
import styles from "./suggestions.module.css"

function label(item: Suggestion) {
  return item.unit ? `${item.name}, ${item.unit}` : item.name
}

function taken(item: Suggestion, extras: readonly { name: string }[]) {
  const name = item.name.toLowerCase()
  return extras.some((extra) => extra.name.toLowerCase().startsWith(name))
}

export function Suggestions({
  flow,
  custom,
}: {
  readonly flow: RagWorkflowState
  readonly custom: (line: string) => void
}) {
  const { t } = useTranslation(["rag"])
  const session = flow.session
  const code = session?.position?.code
  const query = useQuery({
    queryKey: ["suggestions", session?.id, code],
    enabled: Boolean(session?.extras_allowed && code),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
    queryFn: async ({ signal }) =>
      unwrap(
        await api.POST("/sessions/{session_id}/suggestions", {
          params: { path: { session_id: session?.id ?? "" } },
          signal,
        }),
      ),
  })
  if (!session?.extras_allowed || !code) return null
  const items = (query.data?.items ?? []).filter((item) => !taken(item, session.extras))
  if (query.isSuccess && !items.length) return null
  function add(item: Suggestion, value: string) {
    flow.addExtra({ name: label(item), value, reason: item.why }, () => undefined)
  }
  return (
    <section className={styles.suggestions} aria-label={t("rag:suggestTitle")}>
      <div className={styles.top}>
        <Icon name="spark" />
        <div>
          <h4>{t("rag:suggestTitle")}</h4>
          <p>{t("rag:suggestHint")}</p>
        </div>
      </div>
      {query.isPending && (
        <p role="status" className={styles.status}>
          <Spinner />
          {t("rag:suggestLoading")}
        </p>
      )}
      {query.isError && (
        <div role="alert" className={styles.status}>
          <p>{t("rag:suggestError")}</p>
          <Button variant="ghost" onClick={() => void query.refetch()}>
            {t("rag:catalogRetry")}
          </Button>
        </div>
      )}
      {items.length > 0 && (
        <ul className={styles.list}>
          {items.map((item) => (
            <li key={item.name} className={styles.item}>
              <div className={styles.head}>
                <strong>
                  <BackendText>{label(item)}</BackendText>
                </strong>
                <span className={styles.source} data-source={item.share == null ? "ai" : "ste"}>
                  {item.share == null
                    ? t("rag:suggestAi")
                    : t("rag:suggestShare", { share: Math.round(item.share * 100) })}
                </span>
              </div>
              {item.why && (
                <p className={styles.why}>
                  <BackendText>{item.why}</BackendText>
                </p>
              )}
              <div className={styles.chips}>
                {item.value && (
                  <Button
                    variant="primary"
                    icon="plus"
                    className={styles.chip}
                    disabled={flow.busy}
                    title={t("rag:suggestEvidence", { quote: item.evidence })}
                    onClick={() => add(item, item.value)}
                  >
                    {t("rag:suggestFromDescription", { value: item.value })}
                  </Button>
                )}
                {item.options
                  .filter((option) => option !== item.value)
                  .map((option) => (
                    <Button
                      key={option}
                      className={styles.chip}
                      disabled={flow.busy}
                      onClick={() => add(item, option)}
                    >
                      <BackendText>{option}</BackendText>
                    </Button>
                  ))}
                <Button
                  variant="ghost"
                  icon="edit"
                  className={styles.chip}
                  disabled={flow.busy}
                  onClick={() => custom(`${label(item)} = `)}
                >
                  {t("rag:suggestOwn")}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
