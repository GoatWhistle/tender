import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type Facet, type ProductPage, type Sort } from "../api";
import { CardSkeleton, ProductCard } from "../components/ProductCard";
import { Empty, ErrorBlock } from "../components/States";
import { bySlug } from "../lib/categories";
import { plural, shortLabel } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const SORTS: [Sort, string][] = [
  ["relevance", "По умолчанию"],
  ["price_asc", "Сначала дешевле"],
  ["price_desc", "Сначала дороже"],
  ["filled", "Полнее заполнены"],
];

/** Фильтры в адресе: `f=<код характеристики>:<код значения>`. */
function readFilters(params: URLSearchParams): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const f of params.getAll("f")) {
    const [ch, v] = f.split(":");
    if (ch && v) (out[ch] ??= []).push(v);
  }
  return out;
}

function FacetGroup({
  facet,
  selected,
  toggle,
  initiallyOpen,
}: {
  facet: Facet;
  selected: string[];
  toggle: (value: string) => void;
  initiallyOpen: boolean;
}) {
  const [open, setOpen] = useState(false);
  const LIMIT = 6;
  const shown = open ? facet.values : facet.values.slice(0, LIMIT);
  return (
    <details className="facet facet--fold" open={initiallyOpen || selected.length > 0}>
      <summary className="facet__name">
        {facet.name}
        {selected.length > 0 && ` · ${selected.length}`}
      </summary>
      {shown.map((v) => (
        <label key={v.code} className="check">
          <input
            type="checkbox"
            checked={selected.includes(v.code)}
            onChange={() => toggle(v.code)}
          />
          <span className="check__box" aria-hidden="true" />
          <span className="check__label">{shortLabel(v.label, v.unit)}</span>
          <span className="check__count">{v.count}</span>
        </label>
      ))}
      {facet.values.length > LIMIT && (
        <button className="textlink facet__more" onClick={() => setOpen(!open)}>
          {open ? "Свернуть" : `Ещё ${facet.values.length - LIMIT}`}
        </button>
      )}
    </details>
  );
}

function Filters({
  data,
  params,
  update,
}: {
  data: ProductPage;
  params: URLSearchParams;
  update: (fn: (p: URLSearchParams) => void) => void;
}) {
  const position = params.get("position");
  const filters = readFilters(params);
  const setPosition = (code: string | null) =>
    update((p) => {
      p.delete("f");
      if (code) p.set("position", code);
      else p.delete("position");
    });
  const toggle = (ch: string, v: string) =>
    update((p) => {
      const key = `${ch}:${v}`;
      const all = p.getAll("f");
      p.delete("f");
      for (const f of all.includes(key) ? all.filter((x) => x !== key) : [...all, key])
        p.append("f", f);
    });

  return (
    <>
      <fieldset className="facet">
        <legend className="facet__name">Позиция КТРУ</legend>
        <label className="check check--radio">
          <input type="radio" name="position" checked={!position} onChange={() => setPosition(null)} />
          <span className="check__box" aria-hidden="true" />
          <span className="check__label">Все позиции</span>
          <span className="check__count">
            {data.positions.reduce((n, p) => n + p.count, 0)}
          </span>
        </label>
        {data.positions.map((p) => (
          <label key={p.code} className="check check--radio">
            <input
              type="radio"
              name="position"
              checked={position === p.code}
              onChange={() => setPosition(p.code)}
            />
            <span className="check__box" aria-hidden="true" />
            <span className="check__label">{p.name}</span>
            <span className="check__count">{p.count}</span>
          </label>
        ))}
      </fieldset>
      {position ? (
        data.facets.map((f, i) => (
          <FacetGroup
            key={f.code}
            initiallyOpen={i < 4}
            facet={f}
            selected={filters[f.code] ?? []}
            toggle={(v) => toggle(f.code, v)}
          />
        ))
      ) : (
        <p className="facet__hint">
          Характеристики у каждой позиции КТРУ свои. Выберите позицию — появятся фильтры по ней.
        </p>
      )}
    </>
  );
}

function ActiveFilters({
  data,
  params,
  update,
}: {
  data: ProductPage;
  params: URLSearchParams;
  update: (fn: (p: URLSearchParams) => void) => void;
}) {
  const chips = params.getAll("f").flatMap((f) => {
    const [ch, v] = f.split(":");
    const facet = data.facets.find((x) => x.code === ch);
    const value = facet?.values.find((x) => x.code === v);
    return facet && value ? [{ f, text: `${facet.name}: ${shortLabel(value.label, value.unit)}` }] : [];
  });
  if (!chips.length) return null;
  return (
    <div className="chips">
      {chips.map((c) => (
        <button
          key={c.f}
          className="chip"
          onClick={() =>
            update((p) => {
              const rest = p.getAll("f").filter((x) => x !== c.f);
              p.delete("f");
              rest.forEach((x) => p.append("f", x));
            })
          }
        >
          {c.text}
          <span aria-hidden="true">×</span>
          <span className="sr-only">— убрать</span>
        </button>
      ))}
      <button className="textlink" onClick={() => update((p) => p.delete("f"))}>
        Сбросить
      </button>
    </div>
  );
}

export function Catalog() {
  const { slug } = useParams();
  const category = bySlug(slug);
  const [params, setParams] = useSearchParams();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const key = params.toString();

  const update = (fn: (p: URLSearchParams) => void) => {
    const next = new URLSearchParams(params);
    fn(next);
    next.delete("page");
    setParams(next);
  };

  const q = params.get("q") ?? "";
  const page = Number(params.get("page") ?? 1);
  const sort = (params.get("sort") as Sort) ?? "relevance";
  const state = useAsync(
    () =>
      api.products({
        category: category?.name,
        position: params.get("position") ?? undefined,
        q: q || undefined,
        filters: readFilters(params),
        sort,
        page,
      }),
    [slug, key],
  );

  if (slug && !category) return <ErrorBlock error={new Error("Нет такой категории")} />;

  const data = state.data;
  const title = category?.name ?? (q ? `«${q}»` : "Каталог");
  const position = data?.positions.find((p) => p.code === params.get("position"));

  return (
    <>
      <section className="pagehead">
        <nav className="crumbs" aria-label="Путь">
          <Link to="/">Главная</Link>
          <span>/</span>
          {category ? <Link to="/catalog">Каталог</Link> : <span>Каталог</span>}
          {category && (
            <>
              <span>/</span>
              <span>{category.name}</span>
            </>
          )}
        </nav>
        <h1 className="pagehead__title">
          {category && <span className="pagehead__index">{category.index}</span>}
          {title}
        </h1>
        <p className="pagehead__sub">
          {position ? (
            <>
              {position.name} · КТРУ {position.code}
            </>
          ) : q && category ? (
            <>Поиск «{q}»</>
          ) : (
            "Товары с характеристиками по справочнику КТРУ"
          )}
        </p>
      </section>

      <div className="catalog">
        <aside className={filtersOpen ? "catalog__filters is-open" : "catalog__filters"}>
          <button
            className="btn btn--outline catalog__toggle"
            aria-expanded={filtersOpen}
            onClick={() => setFiltersOpen(!filtersOpen)}
          >
            Фильтры
          </button>
          <div className="catalog__filters-body">
            {data && <Filters data={data} params={params} update={update} />}
          </div>
        </aside>

        <section className="catalog__results" aria-busy={state.status === "loading"}>
          <div className="toolbar">
            <span className="toolbar__count" aria-live="polite">
              {data
                ? `${data.total} ${plural(data.total, "товар", "товара", "товаров")}`
                : "Загрузка"}
            </span>
            <label className="select">
              <span className="sr-only">Сортировка</span>
              <select
                value={sort}
                onChange={(e) =>
                  update((p) =>
                    e.target.value === "relevance" ? p.delete("sort") : p.set("sort", e.target.value),
                  )
                }
              >
                {SORTS.map(([v, label]) => (
                  <option key={v} value={v}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {data && <ActiveFilters data={data} params={params} update={update} />}

          {state.status === "error" && <ErrorBlock error={state.error} />}
          {data && data.total === 0 && (
            <Empty>
              <p className="notice__title">Ничего не нашлось</p>
              <p>Уберите часть фильтров или измените запрос.</p>
              <button className="btn btn--outline" onClick={() => setParams(new URLSearchParams())}>
                Сбросить всё
              </button>
            </Empty>
          )}
          <div className={state.status === "loading" && data ? "grid is-stale" : "grid"}>
            {data
              ? data.items.map((p) => <ProductCard key={p.id} p={p} />)
              : Array.from({ length: 8 }, (_, i) => <CardSkeleton key={i} />)}
          </div>

          {data && data.pages > 1 && (
            <nav className="pager" aria-label="Страницы">
              {Array.from({ length: data.pages }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  className="pager__page"
                  aria-current={n === data.page ? "page" : undefined}
                  onClick={() => {
                    const next = new URLSearchParams(params);
                    next.set("page", String(n));
                    setParams(next);
                    window.scrollTo({ top: 0 });
                  }}
                >
                  {String(n).padStart(2, "0")}
                </button>
              ))}
            </nav>
          )}
        </section>
      </div>
    </>
  );
}
