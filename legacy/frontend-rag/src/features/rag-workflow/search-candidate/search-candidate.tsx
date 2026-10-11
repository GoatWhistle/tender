import { useTranslation } from "react-i18next"
import type { Search } from "@/entities/rag"
import { Button } from "@/shared/ui/button"
import { CandidateDifferences } from "@/shared/ui/candidate-differences"
import { CategoryIcon } from "@/shared/ui/category-icon/category-icon"
import { Icon } from "@/shared/ui/icon"
import { BackendText } from "@/shared/ui/message"
import styles from "./search-candidate.module.css"

export function SearchCandidate({
  candidate,
  index,
  ready,
  disabled,
  choose,
  best = false,
  rejected = false,
}: {
  readonly candidate: Search["candidates"][number]
  readonly index: number
  readonly ready: boolean
  readonly disabled: boolean
  readonly choose: (code: string) => void
  readonly best?: boolean
  readonly rejected?: boolean
}) {
  const { t } = useTranslation(["rag", "portal"])
  return (
    <div className={styles.row} data-ready={ready} data-rejected={rejected}>
      <span className={styles.lead}>
        <span className={styles.number}>{index + 1}</span>
        <CategoryIcon code={candidate.code} />
      </span>
      <div className={styles.identity}>
        {best && (
          <span className={styles.best}>
            <Icon name="success" size={16} />
            {t("portal:bestMatch")}
          </span>
        )}
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
          title={t("rag:catalogNewTab")}
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
              aria-label={t("rag:choosePosition", { name: candidate.name })}
            />
          </div>
        </>
      )}
    </div>
  )
}
