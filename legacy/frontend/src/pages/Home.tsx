import { Link } from "react-router-dom";
import { api, type PositionSummary, type ProductSummary } from "../api";
import { Arrow, Glyph } from "../components/Glyph";
import { Ring } from "../components/Ring";
import { SpecPlate } from "../components/SpecPlate";
import { ErrorBlock } from "../components/States";
import { CATEGORIES, byName } from "../lib/categories";
import { plural, price } from "../lib/format";
import { useAsync } from "../lib/useAsync";

/** По одному элементу из каждой категории по кругу. */
function roundRobin<T extends { category: string }>(items: T[], n: number): T[] {
  const queues = CATEGORIES.map((c) => items.filter((p) => p.category === c.name));
  const out: T[] = [];
  for (let i = 0; out.length < n && queues.some((q) => q.length > i); i++)
    for (const q of queues) if (q[i] && out.length < n) out.push(q[i]);
  return out;
}

function MiniCard({ p, className }: { p: ProductSummary; className: string }) {
  return (
    <Link to={`/product/${p.id}`} className={`mini ${className}`}>
      <SpecPlate category={p.category} code={p.position_code} />
      <span className="mini__row">
        <span className="mini__text">
          <span className="mini__eyebrow">{p.position_name}</span>
          <span className="mini__title">{p.title}</span>
          <span className="mini__price">от {price(p.price)}</span>
        </span>
        <Ring filled={p.required_filled} total={p.required_total} size={48} />
      </span>
    </Link>
  );
}

function Hero({ total }: { total?: number }) {
  // витрина для героя: самая полная карточка в каждой категории
  const picks = useAsync(
    () =>
      Promise.all(
        CATEGORIES.map((c) => api.products({ category: c.name, sort: "filled", pageSize: 1 })),
      ),
    [],
  );
  const cards = (picks.data ?? []).flatMap((page) => page.items);
  return (
    <section className="hero">
      <h1 className="hero__title">
        Товары для закупок
        <br />с понятными характеристиками
      </h1>
      <p className="hero__text">
        Каждая карточка сверена со справочником КТРУ: одинаковые поля, единицы и значения у всех
        товаров позиции.
      </p>
      <div className="hero__actions">
        <Link className="pill pill--dark" to="/catalog">
          Открыть каталог
        </Link>
        <p className="proof">
          <span className="proof__dot proof__dot--blue" />
          {total ?? "··"} {plural(total ?? 0, "товар", "товара", "товаров")}
          <span className="proof__dot proof__dot--lilac" />3 категории
          <span className="proof__dot proof__dot--green" />
          коды КТРУ
        </p>
      </div>
      <div className="stage" aria-busy={!cards.length}>
        {cards.length === 3 ? (
          <>
            <MiniCard p={cards[1]} className="mini--left" />
            <MiniCard p={cards[0]} className="mini--center" />
            <MiniCard p={cards[2]} className="mini--right" />
          </>
        ) : (
          <div className="mini mini--center mini--ghost" />
        )}
      </div>
    </section>
  );
}

function Positions({ positions }: { positions: PositionSummary[] }) {
  return (
    <section className="section" aria-labelledby="positions-title">
      <h2 id="positions-title" className="label-title">
        Позиции КТРУ в каталоге
      </h2>
      <div className="rail">
        {roundRobin(positions, positions.length).map((p) => (
          <Link
            key={p.code}
            className="tile"
            to={`/catalog/${byName(p.category)?.slug}?position=${p.code}`}
          >
            <SpecPlate category={p.category} code={p.code} size="tile" />
            <span className="tile__title">{p.name}</span>
            <span className="tile__meta">
              {p.products} {plural(p.products, "товар", "товара", "товаров")}
              {p.min_price !== null && ` · от ${price(p.min_price)}`}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function Home() {
  const cats = useAsync(() => api.categories(), []);
  const positions = useAsync(() => api.positions(), []);
  const total = cats.data?.reduce((n, c) => n + c.products, 0);

  return (
    <>
      <Hero total={total} />

      <section className="section section--center">
        <h2 className="label-title">Значения сверены со справочниками</h2>
        <p className="marks">
          <span>КТРУ</span>
          <span>ОКПД2</span>
          <span>ОКЕИ</span>
          <span>ЕИС</span>
        </p>
      </section>

      <section className="section section--center">
        <h2 className="display">
          Одна позиция КТРУ —<br />
          одни характеристики
        </h2>
        <p className="lead">
          Поставщик описывает товар своими словами, система подбирает позицию и приводит значения к
          справочнику. Покупатель фильтрует без «1,2 м» и «120 см» вперемешку.
        </p>
      </section>

      <section className="features" aria-label="Категории">
        {cats.status === "error" && <ErrorBlock error={cats.error} />}
        {CATEGORIES.map((c) => {
          const data = cats.data?.find((x) => x.slug === c.slug);
          return (
            <Link key={c.slug} to={`/catalog/${c.slug}`} className={`feature feature--${c.slug}`}>
              <span className="feature__title">{c.name}</span>
              <span className="feature__text">
                {data
                  ? `${data.positions} ${plural(data.positions, "позиция", "позиции", "позиций")} КТРУ, ${data.products} ${plural(data.products, "товар", "товара", "товаров")}`
                  : "Загрузка"}
              </span>
              <span className="feature__visual">
                <Glyph category={c.name} className="feature__glyph" />
              </span>
              <span className="feature__go" aria-hidden="true">
                <Arrow />
              </span>
            </Link>
          );
        })}
      </section>

      {positions.data && <Positions positions={positions.data} />}

      <section className="section section--center">
        <h2 className="display display--sm">Как читать карточку</h2>
      </section>
      <section className="features" aria-label="Как читать карточку">
        <div className="feature feature--static">
          <span className="feature__title">Полнота</span>
          <span className="feature__text">
            Кольцо показывает, сколько обязательных характеристик позиции заполнил поставщик.
          </span>
          <span className="feature__visual feature__visual--center">
            <Ring filled={4} total={5} size={96} />
          </span>
        </div>
        <div className="feature feature--static">
          <span className="feature__title">Единицы</span>
          <span className="feature__text">
            Размеры, вес и мощность приведены к единицам ОКЕИ из позиции.
          </span>
          <span className="feature__visual feature__visual--center">
            <span className="chip-demo">
              1,2 м <Arrow /> 120 см
            </span>
          </span>
        </div>
        <div className="feature feature--static">
          <span className="feature__title">Код КТРУ</span>
          <span className="feature__text">
            Код позиции можно скопировать в извещение о закупке из карточки товара.
          </span>
          <span className="feature__visual feature__visual--center">
            <span className="chip-demo">31.01.10.000-00000004</span>
          </span>
        </div>
      </section>
    </>
  );
}
