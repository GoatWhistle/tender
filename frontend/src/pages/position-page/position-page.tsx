import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  ragApi,
  type CatalogCharacteristic,
  type CatalogFound,
  type ComparisonRow,
} from "../../entities/rag";
import { useDocumentTitle } from "../../shared/hooks/use-document-title";
import { useResource } from "../../shared/hooks/use-resource";
import { t } from "../../shared/i18n";
import { Banner } from "../../shared/ui/banner/banner";
import { Button } from "../../shared/ui/button/button";
import { TextField } from "../../shared/ui/field/text-field";
import { Icon } from "../../shared/ui/icon/icon";
import { PathLinks } from "../../shared/ui/path/path-links";
import { SkeletonRows } from "../../shared/ui/skeleton/skeleton";
import { StatusBadge } from "../../shared/ui/status-badge/status-badge";
import { Table, type Column } from "../../shared/ui/table/table";
import styles from "./position-page.module.css";

const MAX_COMPARE = 4;

const characteristicColumns = (): readonly Column<CatalogCharacteristic>[] => [
  {
    key: "name",
    label: t("store:position.characteristic"),
    width: "minmax(0, 1fr)",
    render: (c) => (
      <span className={styles.charName}>
        {c.name}
        {c.required && <span className={styles.required}>{t("store:position.required")}</span>}
      </span>
    ),
  },
  {
    key: "values",
    label: t("store:position.values"),
    width: "minmax(0, 2fr)",
    render: (c) =>
      c.values.length ? (
        <ul className={styles.values}>
          {c.values.map((v) => (
            <li key={v} className={styles.valueChip}>
              {v}
            </li>
          ))}
        </ul>
      ) : (
        t("common:noValue")
      ),
  },
];

function cell(value: unknown): string {
  if (Array.isArray(value)) return value.map(cell).join("; ");
  if (value === null || value === undefined || value === "") return "";
  return String(value);
}

function Comparison({ codes }: { readonly codes: readonly string[] }) {
  const result = useResource(() => ragApi.compare(codes), `compare:${codes.join(",")}`);
  const [onlyDiffers, setOnlyDiffers] = useState(true);
  if (result.error)
    return (
      <Banner tone="error" title={t("store:compare.error")}>
        {result.error.message}
      </Banner>
    );
  if (!result.data) return <SkeletonRows label={t("store:compare.loading")} />;
  const { positions, rows } = result.data;
  const shown = onlyDiffers ? rows.filter((r) => r.differs) : rows;
  const columns: Column<ComparisonRow>[] = [
    {
      key: "name",
      label: t("store:compare.field"),
      width: "minmax(0, 1fr)",
      render: (r) =>
        r.field === "okpd2"
          ? t("store:position.okpd2")
          : r.field === "units"
            ? t("store:position.units")
            : (r.name ?? ""),
    },
    ...positions.map((p: CatalogFound, i) => ({
      key: p.code,
      label: p.code,
      width: "minmax(0, 1fr)",
      render: (r: ComparisonRow) => cell(r.values[i]) || t("common:noValue"),
      tone: (r: ComparisonRow) => (r.differs ? ("warning" as const) : ("default" as const)),
    })),
  ];
  return (
    <div className={styles.comparison}>
      <div className={styles.compareTools}>
        <p className={styles.muted}>
          {t("store:compare.summary", {
            differs: rows.filter((r) => r.differs).length,
            total: rows.length,
          })}
        </p>
        <Button variant="ghost" size="sm" onClick={() => setOnlyDiffers(!onlyDiffers)}>
          {t(onlyDiffers ? "store:compare.showAll" : "store:compare.onlyDiffers")}
        </Button>
      </div>
      <Table
        caption={t("store:compare.title")}
        columns={columns}
        rows={shown}
        rowKey={(r) => `${r.field}:${r.name ?? ""}`}
        appear
      />
    </div>
  );
}

export function PositionPage() {
  const { code = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const extra = (params.get("compare") ?? "").split(",").filter(Boolean);
  const codes = [code, ...extra.filter((c) => c !== code)].slice(0, MAX_COMPARE);
  const position = useResource(() => ragApi.position(code), `position:${code}`);
  const [candidate, setCandidate] = useState("");
  useDocumentTitle(position.data?.name ?? code);
  const setCompare = (next: string[]) =>
    setParams((current) => {
      const copy = new URLSearchParams(current);
      if (next.length) copy.set("compare", next.join(","));
      else copy.delete("compare");
      return copy;
    });

  return (
    <div className={styles.page}>
      <PathLinks
        label={t("store:path.label")}
        items={[
          { label: t("store:path.home"), to: "/" },
          { label: t("store:catalog.title"), to: "/catalog" },
          { label: position.data?.name ?? code },
        ]}
      />
      {position.error && (
        <Banner tone="error" title={t("store:position.notFound")}>
          {t("store:position.notFoundText", { code })}
        </Banner>
      )}
      {!position.data && !position.error && <SkeletonRows label={t("store:position.loading")} />}
      {position.data && (
        <>
          <article className={styles.card}>
            <div className={styles.cardHead}>
              <span className={styles.eyebrow}>{t("store:position.eyebrow")}</span>
              <h1 className={styles.title}>{position.data.name}</h1>
              <span className={styles.code}>{position.data.code}</span>
            </div>
            <dl className={styles.facts}>
              <div>
                <dt>{t("store:position.okpd2")}</dt>
                <dd>
                  {position.data.okpd2} {position.data.okpd2_name}
                </dd>
              </div>
              <div>
                <dt>{t("store:position.units")}</dt>
                <dd>{position.data.units.join(", ") || t("common:noValue")}</dd>
              </div>
              <div>
                <dt>{t("store:position.rubrics")}</dt>
                <dd className={styles.rubrics}>
                  {position.data.rubrics.length
                    ? position.data.rubrics.map((r) => (
                        <StatusBadge key={r} tone="info" label={r} />
                      ))
                    : t("common:noValue")}
                </dd>
              </div>
            </dl>
          </article>
          <section className={styles.panel} aria-labelledby="chars-title">
            <h2 id="chars-title" className={styles.blockTitle}>
              {t("store:position.characteristics", {
                count: position.data.characteristics.length,
              })}
            </h2>
            <Table
              caption={t("store:position.characteristicsCaption")}
              columns={characteristicColumns()}
              rows={position.data.characteristics}
              rowKey={(c) => c.code}
            />
          </section>
          <section className={styles.panel} aria-labelledby="compare-title">
            <div className={styles.compareHead}>
              <div>
                <h2 id="compare-title" className={styles.blockTitle}>
                  {t("store:compare.title")}
                </h2>
                <p className={styles.muted}>{t("store:compare.lead")}</p>
              </div>
              <form
                className={styles.addForm}
                onSubmit={(e) => {
                  e.preventDefault();
                  const value = candidate.trim();
                  if (value && !codes.includes(value) && codes.length < MAX_COMPARE) {
                    setCompare([...extra, value]);
                    setCandidate("");
                  }
                }}
              >
                <TextField
                  label={t("store:compare.add")}
                  placeholder={t("store:compare.placeholder")}
                  value={candidate}
                  disabled={codes.length >= MAX_COMPARE}
                  onChange={(e) => setCandidate(e.target.value)}
                />
                <Button
                  type="submit"
                  variant="secondary"
                  icon="plus"
                  disabled={!candidate.trim() || codes.length >= MAX_COMPARE}
                >
                  {t("store:compare.addAction")}
                </Button>
              </form>
            </div>
            {extra.length > 0 && (
              <ul className={styles.chips}>
                {extra.map((c) => (
                  <li key={c} className={styles.chip}>
                    {c}
                    <button
                      type="button"
                      className={styles.chipRemove}
                      aria-label={t("store:compare.remove", { code: c })}
                      onClick={() => setCompare(extra.filter((x) => x !== c))}
                    >
                      <Icon name="close" size={12} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {codes.length > 1 ? (
              <Comparison codes={codes} />
            ) : (
              <p className={styles.muted}>{t("store:compare.empty")}</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
