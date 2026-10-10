import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useRagWorkflow } from "@/entities/rag"
import { ApiError } from "@/shared/api/client"
import { Button } from "@/shared/ui/button"
import { CatalogArtwork } from "@/shared/ui/catalog-artwork/catalog-artwork"
import { Composer } from "@/shared/ui/composer"
import { LoadingNotice } from "@/shared/ui/loading-notice/loading-notice"
import { Stepper } from "@/shared/ui/stepper"
import { Clarification } from "./clarification"
import { Conversation } from "./conversation"
import { DescriptionReview } from "./description-review"
import { MessageReview } from "./message-review/message-review"
import { Narrowing } from "./narrowing"
import { SearchResults } from "./search-results"
import { Specification } from "./specification"
import { Summary } from "./summary"
import { useNarrowing } from "./use-narrowing"
import styles from "./workflow.module.css"

export function RagWorkflow() {
  const { t } = useTranslation(["portal", "rag"])
  const flow = useRagWorkflow()
  const narrowing = useNarrowing(flow.session)
  const [preview, setPreview] = useState(false)
  const input = useRef<HTMLTextAreaElement>(null)
  const scroll = useRef<HTMLDivElement>(null)
  const { search, session } = flow
  const review = search?.stage === "review" && !flow.busy
  const messageReviewId = session?.message_review?.id
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
    if ((stage || messageReviewId) && scroll.current) scroll.current.scrollTop = 0
  }, [stage, messageReviewId])
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
            <div className={styles.examples}>
              <p>{t("portal:examplesTitle")}</p>
              <div>
                {t("portal:examples", { returnObjects: true }).map((example) => (
                  <Button
                    key={example}
                    variant="ghost"
                    icon="plus"
                    onClick={() => {
                      flow.setDraft(example)
                      input.current?.focus()
                    }}
                  >
                    {example}
                  </Button>
                ))}
              </div>
            </div>
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
        {session?.message_review && (
          <MessageReview flow={flow} onEdit={() => input.current?.focus()} />
        )}
        {session && ["clarify", "pick", "failed"].includes(session.stage) && (
          <div className={styles.clarify}>
            <Narrowing steps={narrowing.steps} start={narrowing.start} left={narrowing.left} />
            <Clarification key={session.question?.name ?? session.stage} flow={flow} />
          </div>
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
      <LoadingNotice busy={flow.busy} label={t(status[flow.operation as keyof typeof status])} />
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
