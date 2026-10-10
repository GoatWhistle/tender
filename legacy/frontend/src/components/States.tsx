import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { NotFound } from "../api";

export function ErrorBlock({ error, retry }: { error: Error; retry?: () => void }) {
  if (error instanceof NotFound)
    return (
      <div className="notice">
        <p className="notice__title">Не найдено</p>
        <p>Такой записи в каталоге нет. Возможно, её сняли с витрины.</p>
        <Link className="pill pill--dark" to="/catalog">
          В каталог
        </Link>
      </div>
    );
  return (
    <div className="notice" role="alert">
      <p className="notice__title">Каталог не ответил</p>
      <p>{error.message}</p>
      {retry && (
        <button className="pill pill--dark" onClick={retry}>
          Повторить
        </button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="notice">{children}</div>;
}
