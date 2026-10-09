import { useEffect, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { CATEGORIES } from "../lib/categories";
import { Search as SearchIcon } from "./Glyph";

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
        placeholder="Товар или код КТРУ"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        autoComplete="off"
      />
      <button className="search__go" aria-label="Найти">
        <SearchIcon />
      </button>
    </form>
  );
}

function Nav() {
  return (
    <div className="nav-wrap">
      <a className="skip" href="#main">
        К содержанию
      </a>
      <header className="nav">
        <Link to="/" className="nav__mark" aria-label="Каталог СТЕ — главная">
          <span className="nav__logo" aria-hidden="true" />
          Каталог СТЕ
        </Link>
        <nav className="nav__links" aria-label="Категории">
          <NavLink to="/catalog" end>
            Все товары
          </NavLink>
          {CATEGORIES.map((c) => (
            <NavLink key={c.slug} to={`/catalog/${c.slug}`}>
              {c.name}
            </NavLink>
          ))}
        </nav>
        <Search />
      </header>
    </div>
  );
}

function Footer() {
  return (
    <footer className="footer">
      <div className="footer__brand">
        <p className="footer__name">Каталог СТЕ</p>
        <p className="footer__lead">
          Товары с характеристиками, приведёнными к справочнику КТРУ.
        </p>
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
            <li>КТРУ</li>
            <li>ОКПД2</li>
            <li>ОКЕИ</li>
          </ul>
        </div>
        <div>
          <p className="footer__heading">Поставщику</p>
          <ul>
            <li>Карточка по описанию</li>
            <li>Проверка характеристик</li>
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
