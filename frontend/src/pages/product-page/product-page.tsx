import { useParams } from "react-router-dom";
import { api, type Characteristic, type Product } from "../../api";
import { productColumns } from "../../entities/product";
import { byName } from "../../lib/categories";
import { price, shortLabel, unit } from "../../lib/format";
import { useResource } from "../../shared/hooks/use-resource";
import { useDocumentTitle } from "../../shared/hooks/use-document-title";
import { t } from "../../shared/i18n";
import { Banner } from "../../shared/ui/banner/banner";
import { PathLinks } from "../../shared/ui/path/path-links";
import { Progress } from "../../shared/ui/progress/progress";
import { SkeletonRows } from "../../shared/ui/skeleton/skeleton";
import { Table, type Column } from "../../shared/ui/table/table";
import { CopyCode } from "./copy-code";
import styles from "./product-page.module.css";

function columns(p: Product): Column<Characteristic>[] {
  return [
    {
      key: "name",
      label: t("store:product.name_col"),
      width: "minmax(0, 1.4fr)",
      render: (c) => (
        <span className={styles.nameCell}>
          {c.name}
          {c.required && <span className={styles.sub}>{t("store:product.required")}</span>}
        </span>
      ),
    },
    {
      key: "value",
      label: t("store:product.value_col"),
      width: "minmax(0, 1.4fr)",
      tone: (c) => (p.values[c.code] ? "default" : c.required ? "error" : "muted"),
      render: (c) => {
        const v = p.values[c.code];
        if (!v) return c.required ? t("store:product.missing") : t("common:noValue");
        const allowed = c.values.find((x) => x.code === v.value_code);
        return (
          <span className={styles.nameCell}>
            <span className={styles.value}>{v.number !== null ? v.number : v.label}</span>
            {c.quantitative && allowed && (
              <span className={styles.sub}>
                {t("store:product.ktru", { value: shortLabel(allowed.label, allowed.unit) })}
              </span>
            )}
          </span>
        );
      },
    },
    {
      key: "unit",
      label: t("store:product.unit_col"),
      width: "minmax(0, 0.6fr)",
      render: (c) => unit(p.values[c.code]?.unit ?? c.values.find((v) => v.unit)?.unit ?? null),
    },
  ];
}

function Related({ product }: { readonly product: Product }) {
  const related = useResource(
    () => api.products({ position: product.position_code, pageSize: 6 }),
    `related:${product.id}`,
  );
  const items = related.data?.items.filter((x) => x.id !== product.id).slice(0, 5) ?? [];
  if (!related.loading && items.length === 0) return null;
  return (
    <section className={styles.card} aria-labelledby="related">
      <h2 id="related" className={styles.blockTitle}>
        {t("store:product.related")}
      </h2>
      {related.loading ? (
        <SkeletonRows rows={4} label={t("store:catalog.loading")} />
      ) : (
        <Table
          caption={t("store:product.related")}
          columns={productColumns([])}
          rows={items}
          rowKey={(x) => x.id}
        />
      )}
    </section>
  );
}

export function ProductPage() {
  const { id = "" } = useParams();
  const state = useResource(() => api.product(id), `product:${id}`);
  const p = state.data?.id === id ? state.data : undefined;
  useDocumentTitle(p?.title);

  if (state.error)
    return (
      <div className={styles.page}>
        <Banner tone="error" title={t("store:product.notFound")} />
      </div>
    );
  if (!p)
    return (
      <div className={styles.page}>
        <SkeletonRows rows={6} label={t("store:product.loading")} />
      </div>
    );

  const cat = byName(p.category);
  const chars = [...p.position.characteristics].sort(
    (a, b) => Number(b.required) - Number(a.required),
  );
  const percent = p.required_total ? Math.round((p.required_filled / p.required_total) * 100) : 100;

  return (
    <div className={styles.page}>
      <PathLinks
        label={t("store:path.label")}
        items={[
          { label: t("store:path.home"), to: "/" },
          { label: p.category, to: `/catalog/${cat?.slug ?? ""}` },
          { label: p.position_name, to: `/catalog/${cat?.slug ?? ""}?position=${p.position_code}` },
          { label: p.title },
        ]}
      />
      <section className={styles.card}>
        <h1 className={styles.title}>{p.title}</h1>
        <dl className={styles.facts}>
          <dt>{t("store:product.position")}</dt>
          <dd>
            <span className={styles.code}>{p.position_code}</span> {p.position_name}
          </dd>
          <dt>{t("store:product.category")}</dt>
          <dd>{p.category}</dd>
          <dt>{t("store:product.supplier")}</dt>
          <dd>{p.supplier}</dd>
          <dt>{t("store:product.price")}</dt>
          <dd className={styles.price}>
            {t("store:catalog.priceFrom", { price: price(p.price) })}
            <span className={styles.sub}>{t("store:product.offers", { count: p.offers })}</span>
          </dd>
        </dl>
        <div className={styles.actions}>
          <div className={styles.match}>
            <Progress
              value={p.required_filled}
              max={p.required_total}
              label={t("store:product.matchLabel")}
              caption={t("store:product.match", {
                percent,
                filled: p.required_filled,
                total: p.required_total,
              })}
            />
          </div>
          <CopyCode code={p.position_code} />
        </div>
      </section>
      <section className={styles.card} aria-labelledby="chars">
        <h2 id="chars" className={styles.blockTitle}>
          {t("store:product.characteristics")}
        </h2>
        <Table
          caption={t("store:product.characteristics")}
          columns={columns(p)}
          rows={chars}
          rowKey={(c) => c.code}
        />
      </section>
      <Related product={p} />
    </div>
  );
}
