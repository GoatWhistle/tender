import { useParams, useSearchParams } from "react-router-dom";
import { api, type Sort } from "../../api";
import { productColumns } from "../../entities/product";
import { CatalogFilters, readFilters, readSort, setFacet } from "../../features/catalog-filters";
import { SearchForm } from "../../features/catalog-search";
import { bySlug } from "../../lib/categories";
import { BREAKPOINT, useMediaQuery } from "../../shared/hooks/use-media-query";
import { useResource } from "../../shared/hooks/use-resource";
import { useDocumentTitle } from "../../shared/hooks/use-document-title";
import { t, type MessageKey } from "../../shared/i18n";
import { Collapse, useLoadingIndicator } from "../../shared/motion";
import { Banner } from "../../shared/ui/banner/banner";
import { Button } from "../../shared/ui/button/button";
import { Disclosure } from "../../shared/ui/disclosure/disclosure";
import { Pagination } from "../../shared/ui/pagination/pagination";
import { PathLinks } from "../../shared/ui/path/path-links";
import { Segmented } from "../../shared/ui/segmented/segmented";
import { SkeletonRows } from "../../shared/ui/skeleton/skeleton";
import { Table } from "../../shared/ui/table/table";
import styles from "./catalog-page.module.css";

const SORT_LABEL: Record<Sort, MessageKey> = {
  relevance: "store:catalog.sortRelevance",
  price_asc: "store:catalog.sortPriceAsc",
  price_desc: "store:catalog.sortPriceDesc",
  filled: "store:catalog.sortFilled",
};

export function CatalogPage() {
  const { slug } = useParams();
  const category = bySlug(slug);
  const [params, setParams] = useSearchParams();
  const position = params.get("position");
  const q = params.get("q") ?? "";
  const sort = readSort(params);
  const page = Number(params.get("page") ?? 1);
  const filters = readFilters(params);
  const compact = useMediaQuery(BREAKPOINT.tablet);
  useDocumentTitle(category?.name ?? t("store:catalog.title"));

  const products = useResource(
    () =>
      api.products({
        category: category?.name,
        position: position ?? undefined,
        q: q || undefined,
        filters,
        sort,
        page,
      }),
    `products:${slug}?${params.toString()}`,
  );
  const info = useResource(
    () => (position ? api.position(position) : Promise.resolve(null)),
    `position:${position ?? ""}`,
  );
  const stale = useLoadingIndicator(products.loading && Boolean(products.data), "--delay-skeleton");

  const update = (fn: (p: URLSearchParams) => void, keepPage = false) => {
    const next = new URLSearchParams(params);
    fn(next);
    if (!keepPage) next.delete("page");
    setParams(next);
  };

  if (slug && !category)
    return (
      <div className={styles.page}>
        <Banner tone="warning" title={t("store:catalog.unknownCategory")} />
      </div>
    );

  const data = products.data;
  const columns =
    info.data && info.data.code === position
      ? [...info.data.characteristics]
          .sort((a, b) => Number(b.required) - Number(a.required))
          .slice(0, 3)
      : [];
  const title = category?.name ?? t("store:catalog.title");
  const hasFilters = params.getAll("f").length > 0 || Boolean(position);
  const panel = data && (
    <CatalogFilters
      data={data}
      position={position}
      filters={filters}
      onPosition={(code) =>
        update((p) => {
          p.delete("f");
          if (code) p.set("position", code);
          else p.delete("position");
        })
      }
      onFacet={(ch, values) => update((p) => setFacet(p, ch, values))}
    />
  );

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <PathLinks
          label={t("store:path.label")}
          items={[
            { label: t("store:path.home"), to: "/" },
            category
              ? { label: t("store:path.catalog"), to: "/catalog" }
              : { label: t("store:path.catalog") },
            ...(category ? [{ label: category.name }] : []),
          ]}
        />
        <h1 className={styles.title}>{title}</h1>
        {q && <p className={styles.query}>{t("store:catalog.query", { q })}</p>}
        <SearchForm base={category ? `/catalog/${category.slug}` : "/catalog"} />
      </header>
      <div className={styles.layout}>
        <aside className={styles.aside} aria-label={t("store:catalog.filters")}>
          {panel &&
            (compact ? (
              <Disclosure summary={t("store:catalog.filters")}>{panel}</Disclosure>
            ) : (
              panel
            ))}
          <Collapse open={hasFilters}>
            <Button variant="ghost" size="sm" icon="close" onClick={() => setParams({})}>
              {t("store:catalog.reset")}
            </Button>
          </Collapse>
        </aside>
        <section
          className={styles.results}
          aria-busy={products.loading}
          data-stale={stale || undefined}
        >
          <div className={styles.toolbar}>
            <p className={styles.count} aria-live="polite">
              {data ? t("store:catalog.found", { count: data.total }) : t("store:catalog.loading")}
            </p>
            <Segmented
              label={t("store:catalog.sort")}
              value={sort}
              options={(Object.keys(SORT_LABEL) as Sort[]).map((s) => ({
                value: s,
                label: t(SORT_LABEL[s]),
              }))}
              onChange={(s) =>
                update((p) => (s === "relevance" ? p.delete("sort") : p.set("sort", s)))
              }
            />
          </div>
          <Collapse open={Boolean(products.error)}>
            <Banner tone="error" title={t("store:catalog.error")}>
              {t("store:catalog.errorText")}
            </Banner>
          </Collapse>
          {!data && !products.error && <SkeletonRows rows={8} label={t("store:catalog.loading")} />}
          {data && data.total === 0 && (
            <Banner tone="info" title={t("store:catalog.empty")}>
              {t("store:catalog.emptyText")}
            </Banner>
          )}
          {data && data.total > 0 && (
            <Table
              appear={page === 1}
              caption={title}
              columns={productColumns(columns)}
              rows={data.items}
              rowKey={(p) => p.id}
            />
          )}
          {data && (
            <Pagination
              page={data.page}
              pages={data.pages}
              label={t("store:catalog.pages")}
              pageLabel={(n) => t("store:catalog.page", { n })}
              onChange={(n) => {
                update((p) => p.set("page", String(n)), true);
                window.scrollTo({ top: 0 });
              }}
            />
          )}
        </section>
      </div>
    </div>
  );
}
