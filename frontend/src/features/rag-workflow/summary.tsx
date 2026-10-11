import { useTranslation } from "react-i18next"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { Button } from "@/shared/ui/button"
import { CategoryIcon } from "@/shared/ui/category-icon/category-icon"
import { Illustration } from "@/shared/ui/illustration/illustration"
import { BackendText } from "@/shared/ui/message"
import styles from "./summary.module.css"

export function Summary({
  flow,
  onEdit,
}: {
  readonly flow: RagWorkflowState
  readonly onEdit: () => void
}) {
  const { t } = useTranslation(["rag"])
  const session = flow.session
  if (!session?.position) return null
  const done = session.stage === "done"
  function download() {
    if (!flow.result) return
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(flow.result, null, 2)], { type: "application/json" }),
    )
    const link = document.createElement("a")
    link.href = url
    link.download = `ktru-${session?.position?.code}.json`
    link.click()
    URL.revokeObjectURL(url)
  }
  const details = [
    {
      name: t("rag:catalogOkpd"),
      value: `${session.position.okpd2} ${session.position.okpd2_name}`,
    },
    { name: t("rag:summaryDescription"), value: session.description },
    ...(session.corrected && session.corrected !== session.description
      ? [{ name: t("rag:summaryCorrected"), value: session.corrected }]
      : []),
  ]
  const answers = Object.entries(session.answers).flatMap(([name, value]) =>
    value ? [{ name, value }] : [],
  )
  const groups = [
    { title: "rag:summaryDetails", values: details },
    { title: "rag:summaryAnswers", values: answers },
    {
      title: "rag:fixed",
      values: Object.entries(session.position.fixed).map(([name, value]) => ({ name, value })),
    },
    {
      title: "rag:editable",
      values: session.characteristics.map((field) => ({
        name: field.name,
        value: field.values.join("; ") || t("rag:emptyValue"),
      })),
    },
    { title: "rag:extraTitle", values: session.extras },
  ] as const
  const empty =
    Object.keys(session.position.fixed).length === 0 &&
    session.characteristics.length === 0 &&
    session.extras.length === 0
  return (
    <section className={styles.summary}>
      {done ? (
        <header className={styles.hero}>
          <Illustration name="target" size="md" />
          <h2>{t("rag:done")}</h2>
          <p>{t("rag:doneHint")}</p>
          <div className={styles.heroActions}>
            <Button icon="plus" onClick={flow.reset}>
              {t("rag:new")}
            </Button>
            <Button icon="download" variant="primary" onClick={download} disabled={!flow.result}>
              {t("rag:download")}
            </Button>
          </div>
        </header>
      ) : (
        <>
          <h2>{t("rag:previewTitle")}</h2>
          <p>{t("rag:previewHint")}</p>
        </>
      )}
      <div className={styles.position}>
        <CategoryIcon code={session.position.code} size="xl" />
        <div>
          <h3>
            <BackendText>{session.position.name}</BackendText>
          </h3>
          <p>{session.position.code}</p>
        </div>
      </div>
      {groups
        .filter((group) => group.values.length > 0)
        .map((group) => (
          <section key={group.title}>
            <h3>{t(group.title)}</h3>
            <dl className={styles.values}>
              {group.values.map((item) => (
                <div key={item.name}>
                  <dt>
                    <BackendText>{item.name}</BackendText>
                  </dt>
                  <dd>
                    <BackendText>{item.value}</BackendText>
                    {"reason" in item && item.reason && (
                      <p>
                        <BackendText>{item.reason}</BackendText>
                      </p>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      {empty && <p className={styles.empty}>{t("rag:catalogEmpty")}</p>}
      {!done && (
        <div className={styles.actions}>
          <Button icon="edit" disabled={flow.busy} onClick={onEdit}>
            {t("rag:edit")}
          </Button>
          <Button
            icon="check"
            variant="primary"
            disabled={flow.busy || session.missing.length > 0 || Boolean(flow.draft.trim())}
            onClick={flow.finish}
          >
            {t("rag:finish")}
          </Button>
        </div>
      )}
    </section>
  )
}
