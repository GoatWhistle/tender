import type { CSSProperties } from "react";
import type { Search, SearchCandidate } from "../../../entities/rag";
import { t } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/button/button";
import { Disclosure } from "../../../shared/ui/disclosure/disclosure";
import { Progress } from "../../../shared/ui/progress/progress";
import { Spinner } from "../../../shared/ui/spinner/spinner";
import { Differences } from "./differences";
import styles from "./group-list.module.css";

const transitionName = (c: SearchCandidate) =>
  ({ viewTransitionName: `group-${c.code.replace(/[^a-zA-Z0-9]/g, "-")}` }) as CSSProperties;

function Relevance({ value }: { readonly value: number }) {
  return (
    <span className={styles.relevance}>
      <span className={styles.meter} aria-hidden="true">
        <span className={styles.fill} style={{ "--w": value / 100 } as CSSProperties} />
      </span>
      <span className={styles.percent}>{t("seller:position.relevance", { value })}</span>
    </span>
  );
}

function GroupRow({
  candidate,
  rank,
  best,
  ranked,
  busy,
  onChoose,
}: {
  readonly candidate: SearchCandidate;
  readonly rank: number;
  readonly best: boolean;
  readonly ranked: boolean;
  readonly busy: boolean;
  readonly onChoose: (code: string) => void;
}) {
  return (
    <li className={styles.row} data-best={best || undefined} style={transitionName(candidate)}>
      <span className={styles.rank}>{rank}</span>
      <div className={styles.main}>
        {best && <span className={styles.best}>{t("seller:position.best")}</span>}
        <span className={styles.name}>{candidate.name}</span>
        {candidate.reason && <span className={styles.reason}>{candidate.reason}</span>}
        <span className={styles.meta}>
          <span className={styles.code}>{candidate.code}</span>
          <span>
            {t("seller:position.okpd2")} {candidate.okpd2}
          </span>
        </span>
      </div>
      <div className={styles.side}>
        {ranked && typeof candidate.relevance === "number" && (
          <Relevance value={candidate.relevance} />
        )}
        <Differences differences={candidate.differences} />
      </div>
      <div className={styles.action}>
        <Button
          variant={best ? "primary" : "secondary"}
          size="sm"
          disabled={busy}
          onClick={() => onChoose(candidate.code)}
        >
          {t("seller:position.choose")}
        </Button>
      </div>
    </li>
  );
}

export function GroupList({
  search,
  busy,
  ranking,
  onChoose,
}: {
  readonly search: Search;
  readonly busy: boolean;
  readonly ranking: boolean;
  readonly onChoose: (code: string) => void;
}) {
  const ranked = search.stage === "ranked";
  const total = search.candidates.length + search.rejected.length;
  const left = search.candidates.length;
  return (
    <div className={styles.list} data-ranking={ranking || undefined}>
      <div className={styles.summary}>
        {ranked ? (
          <Progress
            value={total - left}
            max={Math.max(total - 1, 1)}
            label={t("seller:position.narrowingLabel")}
            caption={t("seller:position.groupsLeft", { left, total })}
          />
        ) : (
          <p className={styles.found}>
            {ranking && <Spinner size={16} />}
            {t(ranking ? "seller:position.ranking" : "seller:position.found", { total })}
          </p>
        )}
      </div>
      <ol className={styles.rows} aria-label={t("seller:position.groups")}>
        {search.candidates.map((c, i) => (
          <GroupRow
            key={c.code}
            candidate={c}
            rank={i + 1}
            best={ranked && i === 0}
            ranked={ranked}
            busy={busy}
            onChoose={onChoose}
          />
        ))}
      </ol>
      {ranked && search.rejected.length > 0 && (
        <Disclosure summary={t("seller:position.rejected", { count: search.rejected.length })}>
          <ul className={styles.rejected}>
            {search.rejected.map((c) => (
              <li key={c.code} className={styles.rejectedRow}>
                <span className={styles.rejectedName}>{c.name}</span>
                {c.reason && <span className={styles.reason}>{c.reason}</span>}
                <span className={styles.code}>{c.code}</span>
                <Button variant="ghost" size="sm" disabled={busy} onClick={() => onChoose(c.code)}>
                  {t("seller:position.choose")}
                </Button>
              </li>
            ))}
          </ul>
        </Disclosure>
      )}
    </div>
  );
}
