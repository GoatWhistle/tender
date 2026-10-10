// Список товаров таблицей: фото нет, сравнивают по характеристикам.
import { Link } from "react-router-dom";
import type { Characteristic, ProductSummary } from "../api";
import { plural, price, unit } from "../lib/format";
import { Ring } from "./Ring";

type Props = {
  items?: ProductSummary[];
  /** характеристики позиции в колонках; без них — колонка с позицией КТРУ */
  columns?: Characteristic[];
  stale?: boolean;
  skeletonRows?: number;
};

function Cell({ p, c }: { p: ProductSummary; c: Characteristic }) {
  const v = p.values[c.code];
  if (!v) return <span className="ptable__none">—</span>;
  return <>{v.number !== null ? `${v.number} ${unit(v.unit)}` : v.label}</>;
}

export function ProductTable({ items, columns = [], stale, skeletonRows = 8 }: Props) {
  const byPosition = columns.length === 0;
  return (
    <div className={stale ? "ptable-wrap is-stale" : "ptable-wrap"}>
      <table className="ptable">
        <thead>
          <tr>
            <th scope="col">Товар</th>
            {byPosition ? (
              <th scope="col">Позиция КТРУ</th>
            ) : (
              columns.map((c) => (
                <th key={c.code} scope="col">
                  {c.name}
                </th>
              ))
            )}
            <th scope="col" className="ptable__fill-h">
              <abbr title="Заполнено обязательных характеристик">Полнота</abbr>
            </th>
            <th scope="col" className="ptable__num">
              Цена
            </th>
          </tr>
        </thead>
        <tbody>
          {items
            ? items.map((p) => (
                <tr key={p.id}>
                  <th scope="row" className="ptable__title">
                    <Link to={`/product/${p.id}`} className="ptable__link">
                      {p.title}
                    </Link>
                    <span className="ptable__sub">{p.supplier}</span>
                  </th>
                  {byPosition ? (
                    <td data-label="Позиция КТРУ">
                      {p.position_name}
                      <span className="ptable__sub ptable__code">{p.position_code}</span>
                    </td>
                  ) : (
                    columns.map((c) => (
                      <td key={c.code} data-label={c.name}>
                        <Cell p={p} c={c} />
                      </td>
                    ))
                  )}
                  <td data-label="Полнота" className="ptable__fill">
                    <Ring filled={p.required_filled} total={p.required_total} size={36} />
                  </td>
                  <td data-label="Цена" className="ptable__num">
                    <span className="ptable__price">от {price(p.price)}</span>
                    <span className="ptable__sub">
                      {p.offers} {plural(p.offers, "поставщик", "поставщика", "поставщиков")}
                    </span>
                  </td>
                </tr>
              ))
            : Array.from({ length: skeletonRows }, (_, i) => (
                <tr key={i} aria-hidden="true" className="ptable__skeleton">
                  <th>
                    <span className="skeleton skeleton--title" />
                  </th>
                  {(byPosition ? [0] : columns).map((_, j) => (
                    <td key={j}>
                      <span className="skeleton skeleton--line" />
                    </td>
                  ))}
                  <td>
                    <span className="skeleton skeleton--dot" />
                  </td>
                  <td>
                    <span className="skeleton skeleton--line" />
                  </td>
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  );
}
