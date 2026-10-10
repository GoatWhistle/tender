import { useTranslation } from "react-i18next"
import type { Search } from "@/entities/rag"
import { Button } from "@/shared/ui/button"
import { CandidateDifferences } from "@/shared/ui/candidate-differences"
import { CategoryIcon } from "@/shared/ui/category-icon/category-icon"
import { BackendText } from "@/shared/ui/message"
import styles from "./search-candidate.module.css"

export function SearchCandidate({
  candidate,
  index,
  ready,
  disabled,
  choose,
}: {
  readonly candidate: Search["candidates"][number]
  readonly index: number
  readonly ready: boolean
  readonly disabled: boolean
  readonly choose: (code: string) => void
}) {
  const { t } = useTranslation("rag")
  return (
    <div className={styles.row} data-ready={ready}>
      <span className={styles.lead}>
        <span className={styles.number}>{index + 1}</span>
        <CategoryIcon code={candidate.code} />
      </span>
      <div className={styles.identity}>
        <Button
          variant="row"
          className={styles.name}
          disabled={disabled}
          onClick={() => choose(candidate.code)}
        >
          <BackendText>{candidate.name}</BackendText>
        </Button>
        <a
          data-rank-code
          className={styles.code}
          href={`/catalog/${encodeURIComponent(candidate.code)}`}
          target="_blank"
          rel="noopener noreferrer"
          title={t("catalogNewTab")}
        >
          {candidate.code}
        </a>
        {ready && candidate.reason && (
          <p>
            <BackendText>{candidate.reason}</BackendText>
          </p>
        )}
      </div>
      {ready && (
        <>
          <div className={styles.comparison} data-rank-differences>
            <CandidateDifferences differences={candidate.differences} compact />
          </div>
          <div className={styles.action} data-rank-arrow>
            <Button
              variant="ghost"
              icon="chevron"
              disabled={disabled}
              onClick={() => choose(candidate.code)}
              aria-label={t("choosePosition", { name: candidate.name })}
            />
          </div>
        </>
      )}
    </div>
  )
}
