import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Product } from "../api";
import { ProductTable } from "../components/ProductTable";
import { Ring } from "../components/Ring";
import { ErrorBlock } from "../components/States";
import { byName } from "../lib/categories";
import { plural, price, shortLabel, unit } from "../lib/format";
import { useAsync } from "../lib/useAsync";

function CopyCode({ code }: { code: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="pill pill--dark"
      onClick={() =>
        navigator.clipboard?.writeText(code).then(() => {
          setDone(true);
          setTimeout(() => setDone(false), 1600);
        })
      }
    >
      <span aria-live="polite">{done ? "Код скопирован" : "Скопировать код КТРУ"}</span>
    </button>
  );
}

function Characteristics({ p }: { p: Product }) {
  const chars = [...p.position.characteristics].sort(
    (a, b) => Number(b.required) - Number(a.required),
  );
  return (
    <section className="specs" aria-labelledby="specs-title">
      <div className="specs__head">
        <h2 id="specs-title" className="section-title">
          Характеристики
        </h2>
        <div className="fill">
          <p className="fill__text">
            Обязательные
            <br />
            заполнены: {p.required_filled} из {p.required_total}
          </p>
          <Ring filled={p.required_filled} total={p.required_total} size={64} />
        </div>
      </div>
      <dl className="specs__table">
        {chars.map((c) => {
          const v = p.values[c.code];
          const allowed = c.values.find((x) => x.code === v?.value_code);
          return (
            <div key={c.code} className={v ? "spec" : "spec spec--missing"}>
              <dt className="spec__name">
                {c.name}
                {c.required && <span className="spec__req">обяз.</span>}
              </dt>
              <dd className="spec__value">
                {v ? (
                  <>
                    <span>{v.number !== null ? `${v.number} ${unit(v.unit)}` : v.label}</span>
                    {c.quantitative && allowed && (
                      <span className="spec__note">
                        КТРУ: {shortLabel(allowed.label, allowed.unit)}
                      </span>
                    )}
                  </>
                ) : (
                  <span className="spec__none">
                    Не указано{c.required ? " — поставщик не заполнил обязательное поле" : ""}
                  </span>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}

function Related({ p }: { p: Product }) {
  const state = useAsync(() => api.products({ position: p.position_code, pageSize: 5 }), [p.id]);
  const items = state.data?.items.filter((x) => x.id !== p.id).slice(0, 4);
  if (items && !items.length) return null;
  return (
    <section className="related" aria-labelledby="related-title">
      <h2 id="related-title" className="section-title">
        Ещё в позиции «{p.position_name}»
      </h2>
      <ProductTable
        items={items}
        columns={[...p.position.characteristics]
          .sort((a, b) => Number(b.required) - Number(a.required))
          .slice(0, 4)}
        skeletonRows={4}
      />
    </section>
  );
}

export function ProductPage() {
  const { id = "" } = useParams();
  const state = useAsync(() => api.product(id), [id]);

  if (state.status === "error") return <ErrorBlock error={state.error} />;
  const p = state.status === "ok" ? state.data : undefined;
  if (!p) return <section className="phero phero--empty" aria-busy="true" />;

  const cat = byName(p.category);
  return (
    <>
      <section className="phero">
        <div className="phero__panel">
          <nav className="crumbs" aria-label="Путь">
            <Link to={`/catalog/${cat?.slug}`}>{p.category}</Link>
            <span>/</span>
            <Link to={`/catalog/${cat?.slug}?position=${p.position_code}`}>{p.position_name}</Link>
          </nav>
          <h1 className="phero__title">{p.title}</h1>
          <dl className="facts">
            <div>
              <dt>Цена</dt>
              <dd className="facts__price">от {price(p.price)}</dd>
            </div>
            <div>
              <dt>Предложения</dt>
              <dd>
                {p.offers} {plural(p.offers, "поставщик", "поставщика", "поставщиков")}
              </dd>
            </div>
            <div>
              <dt>Поставщик</dt>
              <dd>{p.supplier}</dd>
            </div>
            <div>
              <dt>КТРУ</dt>
              <dd>{p.position_code}</dd>
            </div>
            <div>
              <dt>ОКПД2</dt>
              <dd>
                {p.position.okpd2} · {p.position.okpd2_name}
              </dd>
            </div>
            <div>
              <dt>Единица</dt>
              <dd>{p.position.units.join(", ")}</dd>
            </div>
          </dl>
          <CopyCode code={p.position_code} />
        </div>
      </section>
      <Characteristics p={p} />
      <Related p={p} />
    </>
  );
}
