// Экран поставщика: описание своими словами → группа КТРУ → оставшиеся позиции.
// Четыре области: описание и история, характеристики, кандидаты и путь сужения, следующее
// действие. Данные — `SessionState` бэкенда как есть; статусы и счётчики UI не вычисляет.
import { useEffect, useMemo, useSyncExternalStore, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { sellerApi, type SessionState } from "../api";
import { plural } from "../lib/format";
import {
  MAX_TEXT,
  createSellerSession,
  textLength,
  type Failure,
  type SellerSession,
  type SellerView,
} from "../lib/sellerSession";

const EXAMPLES = [
  "Стол письменный угловой, деревянный каркас, столешница ЛДСП, для персонала",
  "Шкаф для одежды металлический, глубина 0,55 м",
  "Электролобзик, мощность 500 Вт, глубина пропила по дереву 80 мм",
  "Бумага для офисной техники А4, плотность 80 г/м²",
];

/** Подписи известных статусов; зарезервированные и незнакомые — нейтральной подписью. */
const STATUS: Record<string, string> = {
  draft: "Ждём описание",
  needs_clarification: "Нужно уточнение",
  resolved: "Позиция определена",
  technical_error: "Технический сбой",
};

const known = (status: string) => Object.hasOwn(STATUS, status);
const statusLabel = (status: string) => (known(status) ? STATUS[status] : "Анализ завершён");
const statusClass = (status: string) => (known(status) ? status : "neutral");
const positions = (n: number) => `${n} ${plural(n, "позиция", "позиции", "позиций")}`;

/** Сессия экрана и её связь с `?s=`: вся синхронизация адреса — здесь. */
function useSellerSession(): [SellerView, SellerSession] {
  const store = useMemo(() => createSellerSession(sellerApi), []);
  const view = useSyncExternalStore(store.subscribe, store.view);
  const [params, setParams] = useSearchParams();
  const urlId = params.get("s");

  // адрес → сессия: открыть по ?s= или сбросить, если параметр убрали (назад в истории)
  useEffect(() => {
    const current = store.view().sessionId;
    if (urlId && urlId !== current) void store.open(urlId);
    if (!urlId && current) store.reset();
  }, [urlId, store]);

  // сессия → адрес: новая сессия попадает в ?s=, сброшенная или не найденная — убирает его;
  // читаем store, а не снимок рендера: open из эффекта выше уже мог сменить сессию
  useEffect(() => {
    const current = store.view().sessionId;
    if (current !== urlId) setParams(current ? { s: current } : {}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- только на смену сессии
  }, [view.sessionId]);

  return [view, store];
}

function Composer({ view, store }: { view: SellerView; store: SellerSession }) {
  const { state, draft, busy } = view;
  const length = textLength(draft.trim());
  const tooLong = length > MAX_TEXT;
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    void store.submit();
  };
  return (
    <form className="composer" onSubmit={submit}>
      {state && state.messages.length > 0 && (
        <ol className="said" aria-label="Уже написано">
          {state.messages.map((m) => (
            <li key={m.id}>{m.text}</li>
          ))}
        </ol>
      )}
      <label htmlFor="describe" className="sr-only">
        {state ? "Дополнить описание" : "Описание товара"}
      </label>
      <textarea
        id="describe"
        className="composer__input"
        rows={state ? 2 : 4}
        value={draft}
        autoFocus
        aria-invalid={tooLong || undefined}
        aria-describedby="describe-hint"
        placeholder={
          state
            ? "Дополните описание: например, «глубина 60 см, каркас металлический»"
            : "Опишите товар своими словами: что это, материал, размеры, мощность…"
        }
        onChange={(e) => store.setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <div className="composer__bar">
        <span id="describe-hint" className={tooLong ? "composer__hint is-over" : "composer__hint"}>
          {length > MAX_TEXT * 0.9
            ? `${length} из ${MAX_TEXT} символов`
            : "Enter — отправить · Shift + Enter — перенос"}
        </span>
        <button className="pill pill--dark" disabled={!draft.trim()}>
          {busy ? "Анализ…" : state ? "Дополнить" : "Подобрать КТРУ"}
        </button>
      </div>
      {!state && (
        <div className="examples" role="group" aria-label="Примеры описаний">
          {EXAMPLES.map((x) => (
            <button key={x} type="button" className="example" onClick={() => store.setDraft(x)}>
              {x}
            </button>
          ))}
        </div>
      )}
    </form>
  );
}

function FailureCard({ failure }: { failure: Failure }) {
  return (
    <article className="card-x card-x--issue" role="alert">
      <p className="card-x__eyebrow">
        <span className="card-x__dot" aria-hidden="true" />
        Сбой
      </p>
      <h2 className="card-x__title">{failure.title}</h2>
      <p className="card-x__text">{failure.text}</p>
      {failure.details.map((d) => (
        <p key={d} className="card-x__quote">
          {d}
        </p>
      ))}
    </article>
  );
}

/** Что делать дальше: по статусу из ответа. Вопросы и ответы — следующими тикетами. */
function NextStep({ state }: { state: SessionState }) {
  const { status, path } = state;
  let title: string;
  let text: string;
  if (status === "draft") {
    title = "Опишите товар";
    text = "Что это, материал, размеры, мощность — своими словами.";
  } else if (!path) {
    title = "Группа КТРУ не найдена";
    text = "Опишите товар подробнее: назначение, материал, ключевые свойства.";
  } else if (status === "needs_clarification") {
    title = `В группе осталось ${positions(path.positions)}`;
    text = "Допишите в описании характеристики, которые отличают ваш товар.";
  } else if (status === "resolved") {
    const chosen = state.candidates.find((c) => !c.excluded);
    title = "Позиция КТРУ определена";
    text = chosen ? `${chosen.code} — «${chosen.name}».` : "Осталась одна позиция.";
  } else {
    title = statusLabel(status);
    text = "Проверьте группу и позиции в карточке справа.";
  }
  return (
    <article className="card-x card-x--step">
      <p className={`status status--${statusClass(status)}`}>
        <span className="status__dot" aria-hidden="true" />
        {statusLabel(status)}
      </p>
      <h2 className="card-x__title">{title}</h2>
      <p className="card-x__text">{text}</p>
      {state.next_question != null && (
        <p className="card-x__text">Уточняющие вопросы пока отвечаются только описанием.</p>
      )}
      {state.warnings.map((w) => (
        <p key={w} className="card-x__quote">
          {w}
        </p>
      ))}
    </article>
  );
}

function NextAction({ view }: { view: SellerView }) {
  const { state, failure } = view;
  if (!failure && (!state || state.status === "technical_error")) return null;
  return (
    <section className="cards" aria-label="Следующее действие" aria-live="polite">
      <div className="cards__item">
        {failure ? <FailureCard failure={failure} /> : state && <NextStep state={state} />}
      </div>
    </section>
  );
}

function Summary({ state, busy }: { state: SessionState; busy: boolean }) {
  const { path, status } = state;
  return (
    <div className="summary">
      <div className="summary__text">
        <p className={`status status--${statusClass(status)}`}>
          <span className="status__dot" aria-hidden="true" />
          {statusLabel(status)}
          {busy && <span className="status__busy">· анализ…</span>}
        </p>
        <p className="summary__title">
          {path?.group.name ??
            (status === "technical_error"
              ? "Анализ не выполнен"
              : status === "draft"
                ? "Группа КТРУ не выбрана"
                : "Группа КТРУ не найдена")}
        </p>
        {path && (
          <p className="summary__code">
            {path.group.code} · {path.category}
          </p>
        )}
      </div>
    </div>
  );
}

function Characteristics({ state }: { state: SessionState }) {
  return (
    <section aria-labelledby="facts-title">
      <h2 id="facts-title" className="block-title">
        Характеристики
      </h2>
      <p className="muted">
        {state.facts.length
          ? `Извлечено: ${state.facts.length}.`
          : "Пока не извлекаются. Здесь появятся значения из описания, приведённые к справочнику КТРУ."}
      </p>
    </section>
  );
}

function Candidates({ state }: { state: SessionState }) {
  const { path, candidates, alternatives, status } = state;
  const { in_group, compatible, excluded_by_rules } = state.candidate_counts;
  return (
    <section aria-labelledby="cands-title">
      <h2 id="cands-title" className="block-title">
        Кандидаты КТРУ
      </h2>
      {!path ? (
        <p className="muted">
          {status === "technical_error"
            ? "Анализ не выполнен из-за сбоя — кандидатов пока нет."
            : status === "draft"
              ? "Появятся после первого описания."
              : "Группа не найдена: допишите описание."}
        </p>
      ) : (
        <>
          <ol className="path" aria-label="Путь сужения">
            <li>
              <span className="path__label">Категория</span>
              {path.category}
            </li>
            <li>
              <span className="path__label">Группа {path.group.code}</span>
              {path.group.name}
            </li>
            <li>
              <span className="path__label">Осталось</span>
              {positions(path.positions)}
            </li>
          </ol>
          <p className="funnel">
            <span>
              В группе <strong>{in_group}</strong>
            </span>
            <span>
              подходят <strong>{compatible}</strong>
            </span>
            {excluded_by_rules > 0 && (
              <span>
                исключено правилами <strong>{excluded_by_rules}</strong>
              </span>
            )}
          </p>
          {candidates.length > 0 && (
            <details className="excluded" open={candidates.length <= 5}>
              <summary>Позиции группы: {candidates.length}</summary>
              <ul className="cands">
                {candidates.map((c) => (
                  <li key={c.code} className={c.excluded ? "cand cand--out" : "cand"}>
                    <span className="cand__name">{c.name}</span>
                    <span className="cand__code">{c.code}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
      {alternatives.length > 0 && (
        <details className="excluded">
          <summary>Другие группы: {alternatives.length}</summary>
          <ul className="cands">
            {alternatives.map((a) => (
              <li key={a.code} className="cand cand--alt">
                <span className="cand__name">{a.name}</span>
                <span className="cand__code">{a.code}</span>
                <span className="cand__reason">{a.category}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

export function Seller() {
  const [view, store] = useSellerSession();
  const { state, busy } = view;

  return (
    <>
      <section className="pagehead pagehead--compact">
        <nav className="crumbs" aria-label="Путь">
          <Link to="/">Главная</Link>
          <span>/</span>
          <span>Поставщику</span>
        </nav>
        <h1 className="pagehead__title">Новая карточка товара</h1>
        <p className="pagehead__sub">
          Опишите товар своими словами — подберём группу КТРУ и покажем, сколько позиций осталось.
        </p>
      </section>

      <div className={state ? "seller seller--split" : "seller"}>
        <div className="seller__input">
          <Composer view={view} store={store} />
          <NextAction view={view} />
          {(state || view.sessionId) && (
            <button type="button" className="textlink seller__reset" onClick={store.reset}>
              Начать новую карточку
            </button>
          )}
        </div>

        {state && (
          <aside
            className={busy ? "seller__card is-stale" : "seller__card"}
            aria-label="Карточка товара"
            aria-busy={busy}
          >
            <Summary state={state} busy={busy} />
            <Characteristics state={state} />
            <Candidates state={state} />
          </aside>
        )}
      </div>
    </>
  );
}
