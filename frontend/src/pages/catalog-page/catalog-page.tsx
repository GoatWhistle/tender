import { Link, useSearchParams } from "react-router-dom";
import { ragApi, type CatalogFound } from "../../entities/rag";
import { SearchForm } from "../../features/catalog-search";
import { useDocumentTitle } from "../../shared/hooks/use-document-title";
import { useResource } from "../../shared/hooks/use-resource";
import { t } from "../../shared/i18n";
import { Banner } from "../../shared/ui/banner/banner";
import { EmptyState } from "../../shared/ui/empty-state/empty-state";
import { PathLinks } from "../../shared/ui/path/path-links";
import { Segmented } from "../../shared/ui/segmented/segmented";
import { SkeletonRows } from "../../shared/ui/skeleton/skeleton";
import { Table, type Column } from "../../shared/ui/table/table";
import styles from "./catalog-page.module.css";

type Mode = "text" | "semantic";

const columns = (): readonly Column<CatalogFound>[] => [
  {
    key: "code",
    label: t("store:catalog.code"),
    width: "minmax(190px, 220px)",
    render: (p) => (
      <Link to={`/catalog/${encodeURIComponent(p.code)}`} className={styles.code}>
        {p.code}
      </Link>
    ),
  },
  {
    key: "name",
    label: t("store:catalog.name"),
    render: (p) => (
      <Link to={`/catalog/${encodeURIComponent(p.code)}`} className={styles.name}>
        {p.name}
      </Link>
    ),
  },
  {
    key: "okpd2",
    label: t("store:catalog.okpd2"),
    width: "minmax(0, 1fr)",
    render: (p) => (
      <span className={styles.okpd}>
        <span className={styles.okpdCode}>{p.okpd2}</span>
        {p.okpd2_name}
      </span>
    ),
  },
];

function Results({ q, mode }: { readonly q: string; readonly mode: Mode }) {
  const found = useResource(() => ragApi.find(q, mode), `catalog:${mode}:${q}`);
  if (found.error)
    return (
      <Banner tone="error" title={t("store:catalog.error")}>
        {t("store:catalog.errorText")}
      </Banner>
    );
  if (!found.data) return <SkeletonRows label={t("store:catalog.loading")} />;
  if (found.data.length === 0)
    return (
      <EmptyState illustration="magnifier" title={t("store:catalog.empty")}>
        {t("store:catalog.emptyText")}
      </EmptyState>
    );
  return (
    <>
      <p className={styles.count}>{t("store:catalog.found", { count: found.data.length })}</p>
      <Table
        caption={t("store:catalog.results")}
        columns={columns()}
        rows={found.data}
        rowKey={(p) => p.code}
        appear
      />
    </>
  );
}

export function CatalogPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q")?.trim() ?? "";
  const mode: Mode = params.get("mode") === "semantic" ? "semantic" : "text";
  useDocumentTitle(q ? t("store:catalog.query", { q }) : t("store:catalog.title"));
  return (
    <div className={styles.page}>
      <PathLinks
        label={t("store:path.label")}
        items={[{ label: t("store:path.home"), to: "/" }, { label: t("store:catalog.title") }]}
      />
      <header className={styles.head}>
        <h1 className={styles.title}>{t("store:catalog.title")}</h1>
        <p className={styles.lead}>{t("store:catalog.lead")}</p>
      </header>
      <section className={styles.panel}>
        <div className={styles.tools}>
          <div className={styles.search}>
            <SearchForm />
          </div>
          <Segmented
            label={t("store:catalog.mode")}
            value={mode}
            options={[
              { value: "text", label: t("store:catalog.modeText") },
              { value: "semantic", label: t("store:catalog.modeSemantic") },
            ]}
            onChange={(next) =>
              setParams((current) => {
                const copy = new URLSearchParams(current);
                copy.set("mode", next);
                return copy;
              })
            }
          />
        </div>
        {q ? (
          <Results q={q} mode={mode} />
        ) : (
          <EmptyState illustration="magnifier" title={t("store:catalog.hintTitle")}>
            {t("store:catalog.hint")}
          </EmptyState>
        )}
      </section>
    </div>
  );
}
