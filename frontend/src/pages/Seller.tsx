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
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!text.trim() || busy) return;
    onSubmit(text.trim());
    setText("");
  };
  return (
    <form className="panel composer" onSubmit={submit}>
      <label htmlFor="describe" className="panel__title">
        {state ? "Дополнить описание" : "Опишите товар"}
      </label>
      <textarea
        id="describe"
        className="composer__input"
        rows={state ? 3 : 5}
        value={text}
        placeholder={
          state
            ? "Например: глубина 60 см, каркас металлический"
            : "Название товара и характеристики своими словами: материал, размеры, мощность…"
        }
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
        }}
      />
      <div className="composer__row">
        <button className="pill pill--dark" disabled={busy || !text.trim()}>
          {state ? "Дополнить" : "Подобрать КТРУ"}
        </button>
        <span className="composer__hint">Ctrl + Enter</span>
      </div>
      {!state && (
        <div className="examples">
          <p className="examples__title">Примеры</p>
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

function NextAction({
  state,
  busy,
  answer,
  exportCard,
}: {
  state: SessionState;
  busy: boolean;
  answer: (questionId: string, option: string | null) => void;
  exportCard: () => void;
}) {
  const q = state.next_question;
  if (q)
    return (
      <section className="panel next" aria-labelledby="next-title">
        <p className="next__eyebrow">Следующий шаг</p>
        <h2 id="next-title" className="next__title">
          {q.text}
        </h2>
        {q.hint && <p className="next__hint">{q.hint}</p>}
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
          <button className="textlink" disabled={busy} onClick={() => answer(q.id, null)}>
            Не знаю — пропустить
          </button>
        )}
      </section>
    );

  if (state.status === "no_match") {
    const issue = state.issues.find((i) => i.kind === "no_match");
    return (
      <section className="panel next next--warn">
        <p className="next__eyebrow">Что сделать</p>
        <h2 className="next__title">{issue?.title ?? "Товар не распознан"}</h2>
        <p className="next__hint">{issue?.detail}</p>
      </section>
    );
  }

  const done = state.status === "complete";
  return (
    <section className={done ? "panel next next--done" : "panel next"}>
      <p className="next__eyebrow">{done ? "Готово" : "Черновик"}</p>
      <h2 className="next__title">
        {done
          ? "Все обязательные характеристики заполнены"
          : `Не заполнено: ${state.missing_required.join(", ")}`}
      </h2>
      <p className="next__hint">
        {done
          ? "Проверьте значения в таблице и выгрузите карточку."
          : "Без этих характеристик карточку можно сохранить только черновиком. Допишите их в описании или выберите значение в таблице."}
      </p>
      <button className="pill pill--dark" disabled={busy} onClick={exportCard}>
        {done ? "Выгрузить карточку" : "Сохранить черновик"}
      </button>
    </section>
  );
}

function History({ state }: { state: SessionState }) {
  return (
    <section className="history" aria-label="История уточнений">
      <p className="panel__title">История</p>
      <ol>
        {state.messages.map((m, i) => (
          <li key={i} className={`bubble bubble--${m.role}`}>
            {m.text}
          </li>
        ))}
      </ol>
    </section>
  );
}

function Issues({ issues }: { issues: Issue[] }) {
  const shown = issues.filter((i) => i.kind !== "no_match");
  if (!shown.length) return null;
  return (
    <section className="issues" aria-labelledby="issues-title">
      <h2 id="issues-title" className="block-title">
        Проверка: {shown.length} {plural(shown.length, "замечание", "замечания", "замечаний")}
      </h2>
      <ul>
        {shown.map((i) => (
          <li key={i.id} className={`issue issue--${i.kind}`}>
            <span className="issue__dot" aria-hidden="true" />
            <div>
              <p className="issue__title">{i.title}</p>
              <p className="issue__detail">{i.detail}</p>
              {i.quote && <p className="issue__quote">«{i.quote}»</p>}
            </div>
          </li>
        ))}
      </ul>
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
                <th scope="col">Источник</th>
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
                    <td data-label="Источник" className="ftable__source">
                      {f ? SOURCE[f.source] : "Не указано"}
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

function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function Seller() {
  const { state, busy, error, run, reset } = useSession();
  const id = state?.session_id;

  const exportCard = async () => {
    if (!id) return;
    const card = await sellerApi.export(id);
    download(`${card.draft ? "draft" : "card"}-${card.position_code ?? id}.json`, card);
  };

  return (
    <>
      <section className="pagehead">
        <nav className="crumbs" aria-label="Путь">
          <Link to="/">Главная</Link>
          <span>/</span>
          <span>Поставщику</span>
        </nav>
        <h1 className="pagehead__title">Новая карточка товара</h1>
        <p className="pagehead__sub">
          Опишите товар своими словами — подберём позицию КТРУ, приведём значения и единицы к
          справочнику и подскажем, чего не хватает.
        </p>
      </section>

      <div className="seller">
        <div className="seller__side">
          <Composer
            state={state}
            busy={busy}
            onSubmit={(text) =>
              run(() => (id ? sellerApi.message(id, text) : sellerApi.create(text)))
            }
          />
          {state && (
            <NextAction
              state={state}
              busy={busy}
              answer={(q, o) => run(() => sellerApi.answer(id!, q, o))}
              exportCard={exportCard}
            />
          )}
          {state && <History state={state} />}
          {state && (
            <button className="textlink seller__reset" onClick={reset}>
              Начать новую карточку
            </button>
          )}
        </div>

        <div className={busy && state ? "seller__main is-stale" : "seller__main"} aria-busy={busy}>
          {error && (
            <div className="notice" role="alert">
              <p className="notice__title">Не получилось</p>
              <p>{error}</p>
            </div>
          )}
          {!state && !busy && (
            <div className="seller__empty">
              <p className="block-title">Здесь появится карточка</p>
              <p className="muted">
                Характеристики с цитатами из описания, единицы по ОКЕИ, кандидаты КТРУ и
                замечания — после первого описания.
              </p>
            </div>
          )}
          {!state && busy && <div className="seller__empty skeleton" style={{ height: 320 }} />}
          {state && (
            <>
              <Summary state={state} busy={busy} />
              <Issues issues={state.issues} />
              <Characteristics
                state={state}
                busy={busy}
                edit={(key, code) => run(() => sellerApi.editFact(id!, key, code))}
              />
              <Candidates state={state} />
            </>
          )}
        </div>
      </div>
    </>
  );
}
