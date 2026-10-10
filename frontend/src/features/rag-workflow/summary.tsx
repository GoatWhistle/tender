import { useTranslation } from "react-i18next"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { Button } from "@/shared/ui/button"
import { Icon } from "@/shared/ui/icon"
import { BackendText } from "@/shared/ui/message"
import { PositionMeta } from "@/shared/ui/position-meta"
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
  const groups = [
    {
      title: "rag:fixed",
      values: Object.entries(session.position.fixed).map(([name, value]) => ({ name, value })),
    },
    {
      title: "rag:editable",
      values: session.characteristics.map((field) => ({
        name: field.name,
        value: field.numeric
          ? field.numeric.exact
            ? `${field.numeric.exact} ${field.numeric.unit}`
            : t("rag:emptyValue")
          : field.values.join("; ") || t("rag:emptyValue"),
      })),
    },
    { title: "rag:extraTitle", values: session.extras },
  ] as const
  return (
    <section className={styles.summary}>
      {done && <Icon name="success" size={32} />}
      <h2>{t(done ? "rag:done" : "rag:previewTitle")}</h2>
      <p>{t(done ? "rag:doneHint" : "rag:previewHint")}</p>
      <h3>
        <BackendText>{session.position.name}</BackendText>
      </h3>
      <PositionMeta
        code={session.position.code}
        okpd2={session.position.okpd2}
        okpd2Name={session.position.okpd2_name}
      />
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
      <div className={styles.actions}>
        {done ? (
          <>
            <Button icon="plus" onClick={flow.reset}>
              {t("rag:new")}
            </Button>
            <Button icon="download" variant="primary" onClick={download} disabled={!flow.result}>
              {t("rag:download")}
            </Button>
          </>
        ) : (
          <>
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
          </>
        )}
      </div>
    </section>
  )
}
