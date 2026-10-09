import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type PositionSummary } from "../api";
import { Arrow, Triangle } from "../components/Glyph";
import { UtilityStrip } from "../components/Shell";
import { SpecPlate } from "../components/SpecPlate";
import { ErrorBlock } from "../components/States";
import { CATEGORIES, byName } from "../lib/categories";
import { plural, price } from "../lib/format";
import { useAsync } from "../lib/useAsync";

/** По одной позиции из каждой категории по кругу. */
function roundRobin(positions: PositionSummary[], n: number): PositionSummary[] {
  const queues = CATEGORIES.map((c) => positions.filter((p) => p.category === c.name));
  const out: PositionSummary[] = [];
  for (let i = 0; out.length < n && queues.some((q) => q.length > i); i++)
    for (const q of queues) if (q[i] && out.length < n) out.push(q[i]);
  return out;
}

function Hero({ featured }: { featured: PositionSummary[] }) {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (paused || featured.length < 2) return;
    const t = setInterval(() => setI((x) => (x + 1) % featured.length), 6000);
    return () => clearInterval(t);
  }, [paused, featured.length]);

  const p = featured[i];
  if (!p) return <section className="hero hero--empty" aria-busy="true" />;
  return (
    <section
      className="hero"
      aria-roledescription="карусель"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className="hero__visual">
        <SpecPlate key={p.code} category={p.category} code={p.code} caption={p.okpd2} size="hero" />
      </div>
      <div className="hero__panel">
        <p className="eyebrow">
          {byName(p.category)?.index} · {p.category}
        </p>
        <div key={p.code} className="hero__copy">
          <h1 className="hero__title">{p.name}</h1>
          <p className="hero__text">
            {p.okpd2_name}. {p.products} {plural(p.products, "товар", "товара", "товаров")} в
            каталоге
            {p.min_price !== null && <>, от {price(p.min_price)}</>}.
          </p>
          <Link className="discover" to={`/catalog/${byName(p.category)?.slug}?position=${p.code}`}>
            <span className="discover__icon">
              <Triangle />
            </span>
            Смотреть товары позиции
          </Link>
        </div>
        <div className="rail" role="tablist" aria-label="Позиции на главной">
          {featured.map((f, n) => (
            <button
              key={f.code}
              role="tab"
              aria-selected={n === i}
              aria-label={f.name}
              className="rail__stop"
              onClick={() => setI(n)}
            >
              {String(n + 1).padStart(2, "0")}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Home() {
  const cats = useAsync(() => api.categories(), []);
  const positions = useAsync(() => api.positions(), []);
  const all = positions.data ?? [];
  const featured = roundRobin(all, 4);
  const tiles = roundRobin(
    all.filter((p) => !featured.includes(p)),
    4,
  );

  return (
    <>
      <Hero featured={featured} />
      <UtilityStrip />

      <section className="intro">
        <h2 className="intro__title">Каждая карточка приведена к справочнику КТРУ</h2>
        <p className="intro__text">
          Поставщик описывает товар своими словами — система подбирает позицию КТРУ, сопоставляет
          значения и единицы. Покупатель видит одинаковые характеристики у всех товаров позиции и
          фильтрует по ним без «1,2 м» и «120 см» вперемешку.
        </p>
        <Link className="discover discover--dark" to="/catalog">
          <span className="discover__icon">
            <Triangle />
          </span>
          Весь каталог
        </Link>
      </section>

      <section className="index" aria-label="Категории">
        {cats.status === "error" && <ErrorBlock error={cats.error} />}
        {CATEGORIES.map((c) => {
          const data = cats.data?.find((x) => x.slug === c.slug);
          return (
            <Link key={c.slug} to={`/catalog/${c.slug}`} className="index__row">
              <span className="index__label">
                {c.name}
                <sup className="index__count">{data ? data.products : "··"}</sup>
              </span>
              <span className="index__sub">
                {data
                  ? `${data.positions} ${plural(data.positions, "позиция", "позиции", "позиций")} КТРУ`
                  : "Загрузка"}
              </span>
              <Triangle className="index__arrow" />
            </Link>
          );
        })}
      </section>

      {tiles.length > 0 && (
        <section className="tiles" aria-label="Позиции КТРУ">
          {tiles.map((p) => (
            <Link
              key={p.code}
              className="tile"
              to={`/catalog/${byName(p.category)?.slug}?position=${p.code}`}
            >
              <SpecPlate category={p.category} code={p.code} />
              <span className="tile__text">
                <span className="tile__eyebrow">{p.code}</span>
                <span className="tile__title">{p.name}</span>
                <Arrow className="tile__arrow" />
              </span>
            </Link>
          ))}
        </section>
      )}
    </>
  );
}
