// Карточка поставщика: описание своими словами → характеристики по КТРУ → код позиции.
// Четыре области из плана (раздел 13): описание и история, характеристики, кандидаты КТРУ,
// следующее действие.
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { sellerApi, type Fact, type Issue, type SessionState } from "../api";
import { Ring } from "../components/Ring";
import { plural, shortValue } from "../lib/format";

const EXAMPLES = [
  "Стол письменный угловой, деревяный каркас, столешница ЛДСП, для персонала",
  "Шкаф для одежды металлический, глубина 0,55 м",
  "Электролобзик, мощность 5 кг, толщина дерева 8 см, тип питания: солнечная батарея",
  "Шкаф для одежды",
];

const SOURCE: Record<Fact["source"], string> = {
  description: "Описание",
  answer: "Ответ",
  edit: "Правка",
};

const STATUS: Record<SessionState["status"], string> = {
  no_match: "Товар не распознан",
  needs_clarification: "Нужно уточнение",
  draft: "Черновик",
  complete: "Карточка готова",
};

function useSession() {
  const [params, setParams] = useSearchParams();
  const id = params.get("s");
  const [state, setState] = useState<SessionState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);

  // ответы на устаревшие запросы отбрасываем
  const run = async (call: () => Promise<SessionState>) => {
    const n = ++seq.current;
    setBusy(true);
    setError(null);
    try {
      const next = await call();
      if (n !== seq.current) return;
      setState(next);
      if (next.session_id !== id) setParams({ s: next.session_id }, { replace: true });
    } catch (e) {
      if (n === seq.current) setError((e as Error).message);
    } finally {
      if (n === seq.current) setBusy(false);
    }
  };

  useEffect(() => {
    if (id && state?.session_id !== id) run(() => sellerApi.get(id));
    if (!id) setState(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const reset = () => {
    seq.current++;
    setState(null);
    setError(null);
    setParams({}, { replace: false });
  };

  return { state, busy, error, run, reset };
}

function Composer({
  state,
  busy,
  onSubmit,
}: {
  state: SessionState | null;
  busy: boolean;
  onSubmit: (text: string) => void;
}) {
  const [text, setText] = useState("");
  const said = state?.messages.filter((m) => m.role === "user") ?? [];
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!text.trim() || busy) return;
    onSubmit(text.trim());
    setText("");
  };
  return (
    <form className="composer" onSubmit={submit}>
      {said.length > 0 && (
        <ol className="said" aria-label="Уже написано">
          {said.map((m, i) => (
            <li key={i}>{m.text}</li>
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
        value={text}
        autoFocus
        placeholder={
          state
            ? "Дополните описание: например, «глубина 60 см, каркас металлический»"
            : "Опишите товар своими словами: что это, материал, размеры, мощность…"
        }
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <div className="composer__bar">
        <span className="composer__hint">Enter — отправить · Shift + Enter — перенос</span>
        <button className="pill pill--dark" disabled={busy || !text.trim()}>
          {busy ? "Анализ…" : state ? "Дополнить" : "Подобрать КТРУ"}
        </button>
      </div>
      {!state && (
        <div className="examples" aria-label="Примеры">
          {EXAMPLES.map((x) => (
            <button key={x} type="button" className="example" onClick={() => setText(x)}>
              {x}
            </button>
          ))}
        </div>
      )}
    </form>
  );
}

const ISSUE_LABEL: Record<Issue["kind"], string> = {
  typo: "Опечатка",
  unit: "Не та единица",
  range: "Проверьте значение",
  unknown_value: "Нет в справочнике",
  no_match: "Не распознано",
  not_in_position: "Не из этой позиции",
};

/** Карточки, которые «выпадают» под полем ввода: вопрос, замечания и итог. */
function Cards({
  state,
  busy,
  answer,
  edit,
}: {
  state: SessionState;
  busy: boolean;
  answer: (questionId: string, option: string | null) => void;
  edit: (key: string, valueCode: string | null) => void;
}) {
  const q = state.next_question;
  const cards: { key: string; node: JSX.Element }[] = [];

  if (q)
    cards.push({
      key: q.id,
      node: (
        <article className="card-x card-x--question">
          <p className="card-x__eyebrow">Уточнение</p>
          <h2 className="card-x__title">{q.text}</h2>
          {q.hint && <p className="card-x__text">{q.hint}</p>}
          <div className="options">
            {q.options.map((o) => (
              <button
                key={o.code}
                className="option"
                disabled={busy}
                onClick={() => answer(q.id, o.code)}
              >
                {shortValue(o.label)}
              </button>
            ))}
          </div>
          {q.allow_unknown && (
            <button className="card-x__skip" disabled={busy} onClick={() => answer(q.id, null)}>
              Не знаю — пропустить
            </button>
          )}
        </article>
      ),
    });

  for (const i of state.issues) {
    const options = i.fact_key ? state.editable[i.fact_key] : undefined;
    cards.push({
      key: i.id,
      node: (
        <article className={`card-x card-x--issue card-x--${i.kind}`}>
          <p className="card-x__eyebrow">
            <span className="card-x__dot" aria-hidden="true" />
            {ISSUE_LABEL[i.kind]}
          </p>
          <h2 className="card-x__title">{i.title}</h2>
          <p className="card-x__text">{i.detail}</p>
          {i.quote && <p className="card-x__quote">«{i.quote}»</p>}
          {options && (
            <label className="select card-x__fix">
              <span className="sr-only">Исправить «{i.fact_key}»</span>
              <select
                value=""
                disabled={busy}
                onChange={(e) => edit(i.fact_key!, e.target.value)}
              >
                <option value="" disabled>
                  Выбрать верное значение…
                </option>
                {options.map((o) => (
                  <option key={o.code} value={o.code}>
                    {shortValue(o.label)}
                  </option>
                ))}
              </select>
            </label>
          )}
        </article>
      ),
    });
  }

  if (!q && state.position) {
    const done = state.status === "complete";
    cards.push({
      key: `result-${state.status}`,
      node: (
        <article className={done ? "card-x card-x--done" : "card-x card-x--draft"}>
          <p className="card-x__eyebrow">{done ? "Готово" : "Черновик"}</p>
          <h2 className="card-x__title">
            {done ? "Обязательные характеристики заполнены" : "Не хватает обязательных полей"}
          </h2>
          <p className="card-x__text">
            {done
              ? `Позиция КТРУ ${state.position.code} — «${state.position.name}». Проверьте значения в карточке товара.`
              : `Не заполнено: ${state.missing_required.join(", ")}. Допишите в описании или выберите значение в карточке товара.`}
          </p>
        </article>
      ),
    });
  }

  if (!cards.length) return null;
  return (
    <section className="cards" aria-label="Уточнения и замечания" aria-live="polite">
      {cards.map((c, n) => (
        <div
          key={c.key}
          className="cards__item"
          style={{ animationDelay: `${n * 60}ms` }}
        >
          {c.node}
        </div>
      ))}
    </section>
  );
}

function Characteristics({
  state,
  busy,
  edit,
}: {
  state: SessionState;
  busy: boolean;
  edit: (key: string, valueCode: string | null) => void;
}) {
  const required = new Set(state.required);
  const rows: (Fact | { key: string; name: string; missing: true })[] = [
    ...state.facts,
    ...state.missing_required
      .filter((name) => !state.facts.some((f) => f.key === name))
      .map((name) => ({ key: name, name, missing: true as const })),
  ];
  const free = Object.keys(state.editable).filter((k) => !rows.some((r) => r.key === k));
  const [adding, setAdding] = useState("");

  return (
    <section aria-labelledby="facts-title">
      <h2 id="facts-title" className="block-title">
        Характеристики
      </h2>
      {rows.length === 0 ? (
        <p className="muted">
          Пока ничего не извлечено. Перечислите в описании материал, размеры и другие свойства.
        </p>
      ) : (
        <div className="ptable-wrap">
          <table className="ptable ftable">
            <thead>
              <tr>
                <th scope="col">Характеристика</th>
                <th scope="col">Из описания</th>
                <th scope="col">Значение по КТРУ</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const f = "missing" in r ? null : r;
                const options = state.editable[r.key];
                return (
                  <tr key={r.key} className={f?.state === "error" ? "is-error" : !f ? "is-missing" : ""}>
                    <th scope="row">
                      {r.name}
                      {required.has(r.name) && <span className="spec__req">обяз.</span>}
                    </th>
                    <td data-label="Из описания" className="ftable__quote">
                      {f?.quote ? `«${f.quote}»` : "—"}
                      <span className="ptable__sub">{f ? SOURCE[f.source] : "Не указано"}</span>
                    </td>
                    <td data-label="Значение">
                      {f && (
                        <span className="ftable__value">
                          {f.raw && (
                            <>
                              <span className="ftable__raw">{f.raw}</span>
                              <span aria-label="приведено к">→</span>
                            </>
                          )}
                          <strong>{shortValue(f.value)}</strong>
                          {f.note && <span className="ftable__note">{f.note}</span>}
                        </span>
                      )}
                      {options && (
                        <select
                          className="ftable__select"
                          aria-label={`Изменить «${r.name}»`}
                          disabled={busy}
                          value=""
                          onChange={(e) =>
                            edit(r.key, e.target.value === "__remove" ? null : e.target.value)
                          }
                        >
                          <option value="" disabled>
                            {f ? "Изменить…" : "Выбрать значение…"}
                          </option>
                          {options.map((o) => (
                            <option key={o.code} value={o.code}>
                              {shortValue(o.label)}
                            </option>
                          ))}
                          {f && <option value="__remove">Удалить значение</option>}
                        </select>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {free.length > 0 && (
        <div className="addfact">
          <label className="select">
            <span className="sr-only">Добавить характеристику</span>
            <select value={adding} onChange={(e) => setAdding(e.target.value)} disabled={busy}>
              <option value="">Добавить характеристику…</option>
              {free.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          {adding && (
            <label className="select">
              <span className="sr-only">Значение</span>
              <select
                value=""
                disabled={busy}
                onChange={(e) => {
                  edit(adding, e.target.value);
                  setAdding("");
                }}
              >
                <option value="">Значение…</option>
                {state.editable[adding].map((o) => (
                  <option key={o.code} value={o.code}>
                    {shortValue(o.label)}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      )}
    </section>
  );
}

function Candidates({ state }: { state: SessionState }) {
  const { retrieved, compatible, excluded } = state.candidate_counts;
  const ok = state.candidates.filter((c) => c.compatible);
  const out = state.candidates.filter((c) => !c.compatible);
  if (!retrieved) return null;
  return (
    <section aria-labelledby="cands-title">
      <h2 id="cands-title" className="block-title">
        Кандидаты КТРУ
      </h2>
      <div className="funnel" aria-label={`Найдено ${retrieved}, подходят ${compatible}, исключено ${excluded}`}>
        <span>
          Найдено <strong>{retrieved}</strong>
        </span>
        <span className="funnel__bar" aria-hidden="true">
          <span style={{ width: `${(compatible / retrieved) * 100}%` }} />
        </span>
        <span>
          подходят <strong>{compatible}</strong>
        </span>
      </div>
      <ul className="cands">
        {ok.map((c) => (
          <li key={c.code} className={state.position?.code === c.code ? "cand is-chosen" : "cand"}>
            <span className="cand__name">{c.name}</span>
            <span className="cand__code">{c.code}</span>
          </li>
        ))}
      </ul>
      {out.length > 0 && (
        <details className="excluded">
          <summary>
            Исключены: {out.length}
          </summary>
          <ul className="cands">
            {out.map((c) => (
              <li key={c.code} className="cand cand--out">
                <span className="cand__name">{c.name}</span>
                <span className="cand__reason">{c.reason}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function Summary({ state, busy }: { state: SessionState; busy: boolean }) {
  const total = state.required.length;
  return (
    <div className="summary">
      <div className="summary__text">
        <p className={`status status--${state.status}`}>
          <span className="status__dot" aria-hidden="true" />
          {STATUS[state.status]}
          {busy && <span className="status__busy">· анализ…</span>}
        </p>
        <p className="summary__title">{state.position?.name ?? "Позиция КТРУ не выбрана"}</p>
        <p className="summary__code">
          {state.position
            ? `${state.position.code} · ${state.position.category}`
            : state.candidate_counts.compatible
              ? `${state.candidate_counts.compatible} ${plural(state.candidate_counts.compatible, "кандидат", "кандидата", "кандидатов")}`
              : "Нет кандидатов"}
        </p>
      </div>
      {state.position && (
        <Ring filled={total - state.missing_required.length} total={total} size={64} />
      )}
    </div>
  );
}

export function Seller() {
  const { state, busy, error, run, reset } = useSession();
  const id = state?.session_id;
  const edit = (key: string, code: string | null) => run(() => sellerApi.editFact(id!, key, code));


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
          Опишите товар своими словами — подберём позицию КТРУ, приведём значения к справочнику и
          подскажем, чего не хватает.
        </p>
      </section>

      <div className={state ? "seller seller--split" : "seller"}>
        <div className="seller__input">
          <Composer
            state={state}
            busy={busy}
            onSubmit={(text) =>
              run(() => (id ? sellerApi.message(id, text) : sellerApi.create(text)))
            }
          />

          {error && (
            <div className="notice" role="alert">
              <p className="notice__title">Не получилось</p>
              <p>{error}</p>
            </div>
          )}

          {state && (
            <>
              <Cards
                state={state}
                busy={busy}
                answer={(q, o) => run(() => sellerApi.answer(id!, q, o))}
                edit={edit}
              />
              <button className="textlink seller__reset" onClick={reset}>
                Начать новую карточку
              </button>
            </>
          )}
        </div>

        {state && (
          <aside
            className={busy ? "seller__card is-stale" : "seller__card"}
            aria-label="Карточка товара"
            aria-busy={busy}
          >
            <Summary state={state} busy={busy} />
            <Characteristics state={state} busy={busy} edit={edit} />
            <Candidates state={state} />
          </aside>
        )}
      </div>
    </>
  );
}
