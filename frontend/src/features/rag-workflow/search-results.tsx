import { useEffect, useRef } from "react"
import { useTranslation } from "react-i18next"
import type { Search } from "@/entities/rag"
import { useRankedMotion } from "@/shared/motion/use-ranked-motion"
import { useRankedReveal } from "@/shared/motion/use-ranked-reveal"
import { RejectedCandidates } from "./search-candidate/rejected-candidates"
import { SearchCandidate } from "./search-candidate/search-candidate"
import styles from "./search-results.module.css"

export function SearchResults({
  search,
  busy,
  choose,
  automatic,
}: {
  readonly search: Search
  readonly busy: boolean
  readonly choose: (code: string, automatic?: boolean) => void
  readonly automatic: boolean
}) {
  const { t } = useTranslation(["rag", "portal"])
  const finalized = search.stage === "ranked"
  const { visible, phase, listRef } = useRankedMotion(search.candidates, finalized)
  useRankedReveal(listRef, phase === "ready")
  const attempted = useRef<string | null>(null)
  useEffect(() => {
    if (
      phase === "ready" &&
      !busy &&
      automatic &&
      search.auto_select_code &&
      attempted.current !== search.id
    ) {
      attempted.current = search.id
      choose(search.auto_select_code, true)
    }
  }, [phase, busy, automatic, search.auto_select_code, search.id, choose])
  const kept = new Set(search.candidates.map((item) => item.id))
  return (
    <section className={styles.results} data-state={phase}>
      <h2>{t(finalized ? "portal:rankedTitle" : "portal:rankingTitle")}</h2>
      <ol
        ref={listRef}
        className={styles.list}
        aria-label={t("portal:catalogLabel")}
        aria-busy={busy}
      >
        {visible.map((candidate, index) => (
          <li
            key={candidate.id}
            data-id={candidate.id}
            data-state={phase === "exiting" && !kept.has(candidate.id) ? "exiting" : "entered"}
          >
            <SearchCandidate
              candidate={candidate}
              index={index}
              ready={phase === "ready"}
              disabled={busy || phase !== "ready"}
              choose={choose}
            />
          </li>
        ))}
      </ol>
      {phase === "ready" && (
        <RejectedCandidates candidates={search.rejected} offset={search.candidates.length} />
      )}
      {!visible.length && <p>{t("portal:emptyText")}</p>}
    </section>
  )
}
