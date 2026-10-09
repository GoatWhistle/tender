import { useEffect, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { CATEGORIES } from "../lib/categories";
import { Arrow, Plus } from "./Glyph";

function Search() {
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const navigate = useNavigate();
  useEffect(() => {
    setQ(params.get("q") ?? "");
  }, [params]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    navigate(q.trim() ? `/catalog?q=${encodeURIComponent(q.trim())}` : "/catalog");
  };
  return (
    <form className="search" role="search" onSubmit={submit}>
      <label className="sr-only" htmlFor="search">
        Поиск по каталогу
      </label>
      <input
        id="search"
        className="search__input"
        placeholder="Поиск: товар или код КТРУ"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        autoComplete="off"
      />
      <button className="search__go" aria-label="Найти">
        <Arrow />
      </button>
    </form>
  );
}

function Nav() {
  return (
    <header className="nav">
      <a className="skip" href="#main">
        К содержанию
      </a>
      <nav className="nav__links" aria-label="Категории">
        <NavLink to="/catalog" end>
          Каталог
        </NavLink>
        {CATEGORIES.map((c) => (
          <NavLink key={c.slug} to={`/catalog/${c.slug}`}>
            {c.name}
          </NavLink>
        ))}
      </nav>
      <Link to="/" className="nav__mark" aria-label="Витрина СТЕ — главная">
        СТЕ<span>/</span>КТРУ
      </Link>
      <Search />
    </header>
  );
}

export function UtilityStrip() {
  const items = [
    "Коды КТРУ",
    "Единицы ОКЕИ",
    "Характеристики из справочника",
    "3 категории",
  ];
  return (
    <div className="strip">
      {items.map((t, i) => (
        <span key={t} className="strip__item">
          {i > 0 && <Plus className="strip__plus" />}
          {t}
        </span>
      ))}
    </div>
  );
}

function Footer() {
  const services = [
    ["Унифицированные значения", "Каждое значение — из допустимых значений позиции КТРУ"],
    ["Единицы ОКЕИ", "Размеры, мощность и вес приведены к одной единице"],
    ["Полнота карточки", "Видно, какие обязательные характеристики не заполнены"],
    ["Фильтры по КТРУ", "Подбор по характеристикам выбранной позиции"],
  ];
  return (
    <footer className="footer">
      <div className="footer__services">
        {services.map(([title, text]) => (
          <div key={title} className="footer__service">
            <Plus className="footer__icon" />
            <div>
              <p className="footer__service-title">{title}</p>
              <p>{text}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="footer__cols">
        <div>
          <p className="footer__heading">Каталог</p>
          <ul>
            {CATEGORIES.map((c) => (
              <li key={c.slug}>
                <Link to={`/catalog/${c.slug}`}>{c.name}</Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="footer__heading">Справочники</p>
          <ul>
            <li>КТРУ — каталог товаров, работ, услуг</li>
            <li>ОКПД2</li>
            <li>ОКЕИ — единицы измерения</li>
          </ul>
        </div>
        <div>
          <p className="footer__heading">Поставщику</p>
          <ul>
            <li>Создать карточку по описанию</li>
            <li>Проверить характеристики</li>
          </ul>
        </div>
      </div>
      <div className="footer__legal">
        <span>Tender Hack · Казань · 2026</span>
        <span>Демо-данные: цены и поставщики вымышлены</span>
      </div>
    </footer>
  );
}

export function Shell() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return (
    <>
      <Nav />
      <main id="main" tabIndex={-1}>
        <Outlet />
      </main>
      <Footer />
    </>
  );
}
