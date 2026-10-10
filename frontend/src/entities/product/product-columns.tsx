import { Link } from "react-router-dom";
import type { Characteristic, ProductSummary } from "../../api";
import { price, unit } from "../../lib/format";
import { t } from "../../shared/i18n";
import { Progress } from "../../shared/ui/progress/progress";
import type { Column } from "../../shared/ui/table/table";
import styles from "./product-columns.module.css";

function valueOf(p: ProductSummary, c: Characteristic): string {
  const v = p.values[c.code];
  if (!v) return t("common:noValue");
  return v.number !== null ? `${v.number} ${unit(v.unit)}`.trim() : v.label;
}

export function productColumns(
  characteristics: readonly Characteristic[],
): Column<ProductSummary>[] {
  const title: Column<ProductSummary> = {
    key: "title",
    label: t("store:catalog.product"),
    width: "minmax(0, 2fr)",
    render: (p) => (
      <span className={styles.stack}>
        <Link to={`/product/${p.id}`} className={styles.link}>
          {p.title}
        </Link>
        <span className={styles.sub}>{p.supplier}</span>
      </span>
    ),
  };
  const position: Column<ProductSummary> = {
    key: "position",
    label: t("store:catalog.positionCol"),
    width: "minmax(0, 1.2fr)",
    render: (p) => (
      <span className={styles.stack}>
        {p.position_name}
        <span className={styles.code}>{p.position_code}</span>
      </span>
    ),
  };
  const values = characteristics.map((c): Column<ProductSummary> => ({
    key: c.code,
    label: c.name,
    width: "minmax(0, 1fr)",
    render: (p) => valueOf(p, c),
    tone: (p) => (p.values[c.code] ? "default" : "muted"),
  }));
  const fill: Column<ProductSummary> = {
    key: "fill",
    label: t("store:catalog.fill"),
    width: "minmax(120px, 0.6fr)",
    render: (p) => (
      <Progress
        value={p.required_filled}
        max={p.required_total}
        label={t("store:product.matchLabel")}
        caption={t("store:catalog.fillValue", {
          filled: p.required_filled,
          total: p.required_total,
        })}
      />
    ),
  };
  const cost: Column<ProductSummary> = {
    key: "price",
    label: t("store:catalog.price"),
    width: "minmax(140px, 0.6fr)",
    align: "end",
    render: (p) => (
      <span className={styles.price}>
        {t("store:catalog.priceFrom", { price: price(p.price) })}
        <span className={styles.sub}>{t("store:product.offers", { count: p.offers })}</span>
      </span>
    ),
  };
  return [title, ...(values.length ? values : [position]), fill, cost];
}
