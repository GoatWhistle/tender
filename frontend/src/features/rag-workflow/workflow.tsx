import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useRagWorkflow } from "@/entities/rag"
import { ApiError } from "@/shared/api/client"
import { Spinner } from "@/shared/motion/primitives"
import { Button } from "@/shared/ui/button"
import { CatalogArtwork } from "@/shared/ui/catalog-artwork/catalog-artwork"
import { Composer } from "@/shared/ui/composer"
import { Stepper } from "@/shared/ui/stepper"
import { Clarification } from "./clarification"
import { Conversation } from "./conversation"
import { DescriptionReview } from "./description-review"
import { SearchResults } from "./search-results"
import { Specification } from "./specification"
import { Summary } from "./summary"
import styles from "./workflow.module.css"

export function RagWorkflow() {
  const { t } = useTranslation(["portal", "rag"])
  const flow = useRagWorkflow()
  const [preview, setPreview] = useState(false)
  const input = useRef<HTMLTextAreaElement>(null)
  const scroll = useRef<HTMLDivElement>(null)
  const { search, session } = flow
  const review = search?.stage === "review" && !flow.busy
  const stage = session?.stage ?? search?.stage ?? "start"
  const step = session
    ? session.stage === "done" || preview
      ? 3
      : session.stage === "spec"
        ? 2
        : 1
    : search && search.stage !== "review"
      ? 1
      : 0
  useEffect(() => {
    if (stage && scroll.current) scroll.current.scrollTop = 0
  }, [stage])
  useEffect(() => {
    if (!session) setPreview(false)
  }, [session])
  const status = {
    checking: "rag:checking",
    searching: "rag:searching",
    ranking: "rag:ranking",
    selecting: "rag:selecting",
    answering: "rag:answering",
    updating: "rag:updating",
    validating: "rag:validating",
    saving: "rag:saving",
  } as const
  return (
    <section className={styles.workspace} aria-label={t("portal:workspace")}>
      <Stepper current={step} complete={session?.stage === "done"} />
      <div ref={scroll} className={styles.content}>
        {flow.busy && (
          <div className={styles.loading} role="status">
            <Spinner />
            <div>
              <span>{t(status[flow.operation as keyof typeof status])}</span>
            </div>
          </div>
        )}
        {flow.busy && !search && (
          <div className={styles.waitingArt}>
            <CatalogArtwork />
          </div>
        )}
        {review && <DescriptionReview flow={flow} onEdit={() => input.current?.focus()} />}
        {!search && !flow.busy && !flow.error && (
          <div className={styles.intro}>
            <CatalogArtwork />
            <h2>{t("portal:introTitle")}</h2>
            <p>{t("portal:introText")}</p>
            <Button
              variant="ghost"
              icon="plus"
              onClick={() => {
                flow.setDraft(t("portal:example"))
                input.current?.focus()
              }}
            >
              {t("portal:tryExample")}
            </Button>
          </div>
        )}
        {!session && search && search.stage !== "review" && (
          <SearchResults
            search={search}
            busy={flow.busy}
            choose={flow.choose}
            automatic={flow.automatic}
          />
        )}
        {session && ["clarify", "pick", "failed"].includes(session.stage) && (
          <Clarification key={session.question?.name ?? session.stage} flow={flow} />
        )}
        {session?.stage === "spec" && !preview && (
          <Specification
            flow={flow}
            onPreview={() => {
              setPreview(true)
              if (scroll.current) scroll.current.scrollTop = 0
            }}
          />
        )}
        {session && (preview || session.stage === "done") && (
          <Summary flow={flow} onEdit={() => setPreview(false)} />
        )}
        {flow.error && (
          <div className={styles.error} role="alert">
            <p>
              {t(
                flow.error instanceof ApiError && flow.error.code === "503"
                  ? "rag:unavailable"
                  : "rag:error",
              )}
            </p>
            <Button icon="next" disabled={flow.busy} onClick={flow.retry}>
              {t("portal:retry")}
            </Button>
            <Button variant="ghost" disabled={flow.busy} onClick={flow.reset}>
              {t("rag:new")}
            </Button>
          </div>
        )}
      </div>
      {session ? (
        <Conversation flow={flow} inputRef={input} />
      ) : (
        <Composer
          value={flow.draft}
          onChange={flow.setDraft}
          onSubmit={flow.submit}
          busy={flow.busy}
          started={Boolean(search)}
          inputRef={input}
        />
      )}
    </section>
  )
}
