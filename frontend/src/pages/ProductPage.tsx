import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Product } from "../api";
import { CardSkeleton, ProductCard } from "../components/ProductCard";
import { SpecPlate } from "../components/SpecPlate";
import { ErrorBlock } from "../components/States";
import { byName } from "../lib/categories";
import { plural, price, shortLabel, unit } from "../lib/format";
import { useAsync } from "../lib/useAsync";

function CopyCode({ code }: { code: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="btn btn--outline-light"
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
            Обязательные: {p.required_filled} из {p.required_total}
          </p>
          <div className="fill__bar" aria-hidden="true">
            {Array.from({ length: p.required_total }, (_, i) => (
              <span key={i} className={i < p.required_filled ? "is-on" : ""} />
            ))}
          </div>
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
  const state = useAsync(
    () => api.products({ position: p.position_code, pageSize: 5 }),
    [p.id],
  );
  const items = state.data?.items.filter((x) => x.id !== p.id).slice(0, 4);
  if (items && !items.length) return null;
  return (
    <section className="related" aria-labelledby="related-title">
      <h2 id="related-title" className="section-title">
        Ещё в позиции «{p.position_name}»
      </h2>
      <div className="grid grid--4">
        {items
          ? items.map((x) => <ProductCard key={x.id} p={x} />)
          : Array.from({ length: 4 }, (_, i) => <CardSkeleton key={i} />)}
      </div>
    </section>
  );
}

export function ProductPage() {
  const { id = "" } = useParams();
  const state = useAsync(() => api.product(id), [id]);

  if (state.status === "error") return <ErrorBlock error={state.error} />;
  const p = state.status === "ok" ? state.data : undefined;
  if (!p) return <section className="hero hero--empty" aria-busy="true" />;

  const cat = byName(p.category);
  return (
    <>
      <section className="hero hero--product">
        <div className="hero__visual">
          <SpecPlate category={p.category} code={p.position_code} caption={p.id} size="hero" />
        </div>
        <div className="hero__panel">
          <nav className="crumbs crumbs--light" aria-label="Путь">
            <Link to={`/catalog/${cat?.slug}`}>{p.category}</Link>
            <span>/</span>
            <Link to={`/catalog/${cat?.slug}?position=${p.position_code}`}>{p.position_name}</Link>
          </nav>
          <h1 className="hero__title">{p.title}</h1>
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
