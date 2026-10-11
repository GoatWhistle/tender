import { useState } from "react";
import { t } from "../../../shared/i18n";
import styles from "./differences.module.css";

const VISIBLE = 3;
const HIDDEN = new Set(["ОКПД2", "OKPD2"]);

export function Differences({
  differences,
}: {
  readonly differences: Readonly<Record<string, string>>;
}) {
  const [open, setOpen] = useState(false);
  const entries = Object.entries(differences).filter(([name]) => !HIDDEN.has(name));
  if (entries.length === 0) return null;
  const shown = open ? entries : entries.slice(0, VISIBLE);
  return (
    <div className={styles.differences}>
      <dl className={styles.list}>
        {shown.map(([name, value]) => (
          <div key={name} className={styles.pair}>
            <dt>{name}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {entries.length > VISIBLE && (
        <button
          type="button"
          className={styles.more}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open
            ? t("seller:position.lessDifferences")
            : t("seller:position.moreDifferences", { count: entries.length - VISIBLE })}
        </button>
      )}
    </div>
  );
}
