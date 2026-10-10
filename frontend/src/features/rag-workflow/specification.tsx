import { useId, useState } from "react"
import { useTranslation } from "react-i18next"
import type { Characteristic } from "@/entities/rag"
import type { RagWorkflowState } from "@/entities/rag/use-rag-workflow"
import { Button } from "@/shared/ui/button"
import { CategoryIcon } from "@/shared/ui/category-icon/category-icon"
import { Disclosure } from "@/shared/ui/disclosure"
import { BackendText } from "@/shared/ui/message"
import { CardPreview } from "./characteristics/card-preview"
import { CharacteristicField } from "./characteristics/characteristic-field"
import { FillProgress } from "./characteristics/fill-progress"
import { FixedTiles } from "./characteristics/fixed-tiles"
import { Extras } from "./extras"
import styles from "./specification.module.css"

function rank(field: Characteristic) {
  if (field.values.length) return 2
  return field.required ? 0 : 1
}

function snapshot(code: string, fields: readonly Characteristic[]) {
  const order = fields
    .map((field, index) => ({ name: field.name, rank: rank(field), index }))
    .sort((a, b) => a.rank - b.rank || a.index - b.index)
  return {
    code,
    order: order.map((item) => item.name),
    prefilled: new Set(order.filter((item) => item.rank === 2).map((item) => item.name)),
  }
}

export function Specification({
  flow,
  onPreview,
}: {
  readonly flow: RagWorkflowState
  readonly onPreview: () => void
}) {
  const { t } = useTranslation(["rag"])
  const prefix = useId()
  const session = flow.session
  const code = session?.position?.code ?? ""
  const fields = session?.characteristics ?? []
  const [layout, setLayout] = useState(() => snapshot(code, fields))
  if (layout.code !== code) setLayout(snapshot(code, fields))
  if (!session?.position) return null
  const fixed = Object.entries(session.position.fixed)
  const byName = new Map(fields.map((field) => [field.name, field]))
  const ordered = [
    ...layout.order.flatMap((name) => byName.get(name) ?? []),
    ...fields.filter((field) => !layout.order.includes(field.name)),
  ]
  const done = ordered.filter((field) => layout.prefilled.has(field.name) && field.values.length)
  const open = ordered.filter((field) => !done.includes(field))
  const filled = fields.filter((field) => field.values.length).length
  const fromDescription = fields.filter((field) => field.origin === "description").length
  const id = (name: string) => `${prefix}-${fields.findIndex((field) => field.name === name)}`
  function jump() {
    const target = document.getElementById(id(session?.missing[0] ?? ""))
    if (!target) return
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches
    target.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" })
    target
      .querySelector<HTMLElement>("button:not(:disabled), input")
      ?.focus({ preventScroll: true })
  }
  const render = (field: Characteristic) => (
    <CharacteristicField
      key={field.name}
      id={id(field.name)}
      field={field}
      busy={flow.busy}
      onChange={(values) => flow.values(field.name, values)}
    />
  )
  return (
    <div className={styles.layout}>
      <section className={styles.spec}>
        <header>
          <CategoryIcon code={session.position.code} size="lg" />
          <p>{session.position.code}</p>
          <h2>{t("rag:specTitle")}</h2>
          <h3>
            <BackendText>{session.position.name}</BackendText>
          </h3>
        </header>
        {fields.length > 0 && (
          <div className={styles.status}>
            <FillProgress filled={filled} total={fields.length} />
            <div className={styles.summary}>
              <strong>
                {fromDescription
                  ? t("rag:fromDescription", { count: fromDescription, total: fields.length })
                  : t("rag:filledCount", { filled, total: fields.length })}
              </strong>
              <p>
                {session.missing.length
                  ? t("rag:missing", { count: session.missing.length })
                  : t("rag:allRequired")}
              </p>
            </div>
            {session.missing.length > 0 && (
              <Button variant="secondary" icon="next" onClick={jump}>
                {t("rag:nextMissing")}
              </Button>
            )}
          </div>
        )}
        {session.selection_reason && (
          <p role="status">
            <BackendText>{session.selection_reason}</BackendText>
          </p>
        )}
        {fixed.length > 0 && (
          <section>
            <h3>{t("rag:fixed")}</h3>
            <FixedTiles entries={fixed} />
          </section>
        )}
        <section className={styles.editable}>
          <h3>{t("rag:editable")}</h3>
          {open.length > 0 && <div className={styles.fields}>{open.map(render)}</div>}
          {done.length > 0 && (
            <Disclosure
              title={t("rag:prefilled", { count: done.length })}
              status={null}
              initialOpen={!open.length}
            >
              <div className={styles.fields}>{done.map(render)}</div>
            </Disclosure>
          )}
          {!fields.length && <p>{t("rag:noCharacteristics")}</p>}
        </section>
        <Extras flow={flow} />
        <div className={styles.footer}>
          <Button variant="ghost" icon="back" disabled={flow.busy} onClick={flow.back}>
            {t("rag:backGroups")}
          </Button>
          <div className={styles.actions}>
            {(flow.draft.trim() || session.missing.length > 0) && (
              <strong>
                {flow.draft.trim()
                  ? t("rag:detailsPending")
                  : t("rag:missingFields", { fields: session.missing.join(", ") })}
              </strong>
            )}
            <Button
              variant="primary"
              icon="next"
              disabled={flow.busy || session.missing.length > 0 || Boolean(flow.draft.trim())}
              onClick={onPreview}
            >
              {t("rag:preview")}
            </Button>
          </div>
        </div>
      </section>
      <CardPreview session={session} />
    </div>
  )
}
