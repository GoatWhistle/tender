import { useTranslation } from "react-i18next"
import type { Search } from "@/entities/rag"
import { Disclosure } from "@/shared/ui/disclosure"
import { SearchCandidate } from "./search-candidate"
import styles from "./search-candidate.module.css"

export function RejectedCandidates({
  candidates,
  offset,
}: {
  readonly candidates: Search["rejected"]
  readonly offset: number
}) {
  const { t } = useTranslation("portal")
  if (!candidates.length) return null
  return (
    <Disclosure title={t("rejectedTitle", { count: candidates.length })} status={null}>
      <ol className={styles.rejected} start={offset + 1} aria-label={t("rejectedLabel")}>
        {candidates.map((candidate, index) => (
          <li key={candidate.id}>
            <SearchCandidate candidate={candidate} index={offset + index} ready disabled />
          </li>
        ))}
      </ol>
    </Disclosure>
  )
}
