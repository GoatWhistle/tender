// Экран поставщика: описание своими словами → группа КТРУ → оставшиеся позиции.
// Четыре области: описание и история, характеристики, кандидаты и путь сужения, следующее
// действие. Данные — `SessionState` бэкенда как есть; статусы и счётчики UI не вычисляет.
import {
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type FormEvent,
  type ReactNode,
} from "react";
import { Link, useSearchParams } from "react-router-dom";
import { sellerApi, type EnumProposal, type Question, type SessionState } from "../api";
import { isDiagnostic, type Diagnostic } from "../api/types";
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

/** Подписи известных статусов (тексты — по #3); зарезервированные и незнакомые — нейтральной. */
const STATUS: Record<string, string> = {
  draft: "Ждём описание",
  needs_clarification: "Нужно уточнение",
  resolved: "Код определён",
  ambiguous_in_catalog: "Несколько позиций",
  conflict: "Нет совместимых позиций",
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
            <li key={m.id}>
              <HighlightedMessage
                text={m.text}
                diagnostics={[
                  ...state.errors.filter(isDiagnostic),
                  ...(state.normalizations ?? []),
                ].filter((d) => d.source.message_id === m.id)}
              />
            </li>
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

function HighlightedMessage({ text, diagnostics }: { text: string; diagnostics: Diagnostic[] }) {
  const chars = Array.from(text);
  const spans = diagnostics
    .filter(
      (d) =>
        d.source.start >= 0 &&
        d.source.end <= chars.length &&
        chars.slice(d.source.start, d.source.end).join("") === d.source_quote,
    )
    .sort((a, b) => a.source.start - b.source.start);
  const nodes: ReactNode[] = [];
  let cursor = 0;
  for (const d of spans) {
    if (d.source.start < cursor) continue;
    nodes.push(chars.slice(cursor, d.source.start).join(""));
    nodes.push(
      <mark key={`${d.source.start}:${d.source.end}`} title={d.explanation}>
        {chars.slice(d.source.start, d.source.end).join("")}
      </mark>,
    );
    cursor = d.source.end;
  }
  nodes.push(chars.slice(cursor).join(""));
  return <>{nodes}</>;
}

const DIAGNOSTIC_LABEL = {
  typo: "Возможная опечатка",
  value_not_in_catalog: "Значения нет в проверенной группе",
  out_of_range: "Значение вне допустимых правил",
  synonym: "Нормализация",
};

function Diagnostics({ state }: { state: SessionState }) {
  return (
    <>
      {[...state.errors.filter(isDiagnostic), ...(state.normalizations ?? [])].map((d) => (
        <section className="diagnostic" key={`${d.source.message_id}:${d.source.start}:${d.kind}`}>
          <h3>{DIAGNOSTIC_LABEL[d.kind]}</h3>
          <p className="card-x__quote">
            «{d.source_quote}»{d.suggestion && <> → {d.suggestion}</>}
          </p>
          <p className="card-x__text">{d.explanation}</p>
          {d.candidates.length > 1 && <p>Варианты: {d.candidates.join("; ")}</p>}
          {!d.rule_ref.length && <p className="muted">Гипотеза без привязки к правилу КТРУ.</p>}
          {d.rule_ref.length > 0 && (
            <details>
              <summary>Правила справочника</summary>
              <ul>
                {d.rule_ref.map((r) => (
                  <li key={`${r.position_code}:${r.characteristic_code}`}>
                    {r.position_code}: {r.characteristic_name} ({r.characteristic_code})
                  </li>
                ))}
              </ul>
            </details>
          )}
          {d.requires_confirmation && (
            <p className="muted">Предложение не применено. Проверьте исходное описание.</p>
          )}
        </section>
      ))}
      {state.errors
        .filter((e) => !isDiagnostic(e))
        .map(
          (e) =>
            "code" in e && (
              <p className="card-x__quote" key={e.code} role="status">
                {e.message}
              </p>
            ),
        )}
    </>
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

function QuestionCard({
  question,
  busy,
  onAnswer,
}: {
  question: Question;
  busy: boolean;
  onAnswer: (optionId: string | null) => void;
}) {
  const id = `question-${question.question_id}`;
  return (
    <fieldset className="question" aria-labelledby={id} disabled={busy}>
      <legend id={id} className="card-x__title">
        {question.text}
      </legend>
      <div className="question__options">
        {question.options.map((o) => (
          <button key={o.id} type="button" className="example" onClick={() => onAnswer(o.id)}>
            {o.label}
          </button>
        ))}
        {question.allow_unknown && (
          <button type="button" className="example example--muted" onClick={() => onAnswer(null)}>
            Не знаю
          </button>
        )}
      </div>
    </fieldset>
  );
}

function Missing({ state }: { state: SessionState }) {
  if (state.status !== "resolved") return null;
  if (state.card_complete) return <p className="card-x__text">Карточка заполнена.</p>;
  return (
    <div className="card-x__list">
      <p className="card-x__text">Не заполнены обязательные характеристики:</p>
      <ul>
        {state.missing_required.map((m) => (
          <li key={m.characteristic}>{m.name}</li>
        ))}
      </ul>
    </div>
  );
}

/** Что делать дальше: по статусу и вопросу из ответа; UI ничего не пересчитывает. */
function NextStep({
  state,
  busy,
  onAnswer,
}: {
  state: SessionState;
  busy: boolean;
  onAnswer: (optionId: string | null) => void;
}) {
  const { status, path, next_question: question } = state;
  const compatible = state.candidates.filter((c) => !c.excluded);
  let title: string | null = null;
  let text: string | null = null;
  let list: { key: string; label: string; note?: string }[] = [];
  if (status === "draft") {
    title = "Опишите товар";
    text = "Что это, материал, размеры, мощность — своими словами.";
  } else if (!path) {
    title = "Группа КТРУ не найдена";
    text = "Опишите товар подробнее: назначение, материал, ключевые свойства.";
  } else if (status === "resolved") {
    const chosen = compatible[0];
    title = chosen ? `Код определён: ${chosen.code}` : "Код определён";
    text = chosen ? `«${chosen.name}».` : null;
  } else if (status === "ambiguous_in_catalog") {
    title = `${positions(compatible.length)} не различаются по справочнику`;
    text = state.common_fields.length
      ? "Совпадают по полям: " +
        state.common_fields.map((f) => `${f.characteristic} — ${f.values.join(", ")}`).join("; ") +
        "."
      : "У позиций нет полей, по которым их можно различить.";
    list = compatible.map((c) => ({ key: c.code, label: c.name, note: c.code }));
  } else if (status === "conflict") {
    title = "Ни одна позиция группы не подходит";
    text = "Исправьте значения в описании — причины ниже.";
    list = state.candidates.map((c) => ({ key: c.code, label: c.name, note: c.reason?.text }));
  } else if (status === "needs_clarification" && !question) {
    title = `В группе осталось ${positions(compatible.length)}`;
    text =
      (state.enum_proposals?.length ?? 0) > 0
        ? "Проверьте предложения в блоке «Характеристики»."
        : state.unanswered.length
          ? `Их различают: ${state.unanswered.join(", ")}. Допишите эти сведения в описание.`
          : "Допишите в описании характеристики, которые отличают ваш товар.";
    list = compatible.map((c) => ({ key: c.code, label: c.name, note: c.code }));
  } else if (status !== "needs_clarification") {
    title = statusLabel(status);
    text = "Проверьте группу и позиции в карточке справа.";
  }
  return (
    <article className="card-x card-x--step">
      <p className={`status status--${statusClass(status)}`}>
        <span className="status__dot" aria-hidden="true" />
        {statusLabel(status)}
      </p>
      {title && <h2 className="card-x__title">{title}</h2>}
      {text && <p className="card-x__text">{text}</p>}
      {list.length > 0 && (
        <ul className="cands">
          {list.map((x) => (
            <li key={x.key} className="cand">
              <span className="cand__name">{x.label}</span>
              {x.note && <span className="cand__reason">{x.note}</span>}
            </li>
          ))}
        </ul>
      )}
      <Diagnostics state={state} />
      <Missing state={state} />
      {question && <QuestionCard question={question} busy={busy} onAnswer={onAnswer} />}
      {state.unsupported_rules.length > 0 && (
        <p className="card-x__quote">
          Не проверены правила: {state.unsupported_rules.map((r) => r.characteristic).join(", ")}
        </p>
      )}
      {state.warnings.map((w) => (
        <p key={w} className="card-x__quote">
          {w}
        </p>
      ))}
    </article>
  );
}

function NextAction({ view, store }: { view: SellerView; store: SellerSession }) {
  const { state, failure, busy } = view;
  if (!failure && (!state || state.status === "technical_error")) return null;
  const onAnswer = (optionId: string | null) => void store.answer(optionId);
  return (
    <section className="cards" aria-label="Следующее действие" aria-live="polite">
      {failure && (
        <div className="cards__item">
          <FailureCard failure={failure} />
        </div>
      )}
      {state && state.status !== "technical_error" && (
        <div className="cards__item">
          <NextStep state={state} busy={busy} onAnswer={onAnswer} />
        </div>
      )}
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

const ORIGIN: Record<string, string> = {
  parser: "из описания",
  decision: "сопоставлено по описанию",
  user: "ваш ответ",
  catalog: "из справочника",
};

function Proposal({
  proposal,
  busy,
  store,
}: {
  proposal: EnumProposal;
  busy: boolean;
  store: SellerSession;
}) {
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState<string[]>([]);
  const permits = (selection: string[]) =>
    selection.length > 0 &&
    proposal.selections.some(
      (rule) =>
        (rule.multiple || selection.length === 1) &&
        selection.every((v) => rule.values.includes(v)),
    );
  const multiple = proposal.selections.some((rule) => rule.multiple);
  return (
    <article className="card-x enum-proposal">
      <h3>
        {proposal.characteristic}: {proposal.suggested.join(", ")}
      </h3>
      <p className="status">Предложение · требуется подтверждение</p>
      <p>{proposal.reason}</p>
      {editing && (
        <fieldset disabled={busy}>
          <legend>Выберите {multiple ? "одно или несколько значений" : "одно значение"}</legend>
          {proposal.options.map((value) => (
            <label key={value} className="enum-proposal__option">
              <input
                type={multiple ? "checkbox" : "radio"}
                name={proposal.id}
                checked={values.includes(value)}
                onChange={() =>
                  setValues(
                    multiple
                      ? values.includes(value)
                        ? values.filter((v) => v !== value)
                        : [...values, value]
                      : [value],
                  )
                }
              />
              {value}
            </label>
          ))}
          {values.length > 0 && !permits(values) && (
            <p role="alert">Это сочетание не допускается каталогом.</p>
          )}
          <button
            className="pill pill--dark"
            disabled={!permits(values)}
            onClick={() => void store.resolveEnum(proposal.id, "choose", values)}
          >
            Сохранить выбор
          </button>
        </fieldset>
      )}
      <div className="enum-proposal__actions">
        <button
          className="pill pill--dark"
          disabled={busy || !permits(proposal.suggested)}
          onClick={() => void store.resolveEnum(proposal.id, "accept")}
        >
          Принять
        </button>
        <button className="pill" disabled={busy} onClick={() => setEditing(!editing)}>
          Выбрать другое
        </button>
        <button
          className="pill"
          disabled={busy}
          onClick={() => void store.resolveEnum(proposal.id, "unknown")}
        >
          Не знаю
        </button>
      </div>
    </article>
  );
}

function Characteristics({
  state,
  busy,
  store,
}: {
  state: SessionState;
  busy: boolean;
  store: SellerSession;
}) {
  const facts = state.facts.filter((f) => f.characteristic_name && f.status !== "superseded");
  return (
    <section aria-labelledby="facts-title">
      <h2 id="facts-title" className="block-title">
        Характеристики
      </h2>
      {(state.enum_proposals ?? []).map((proposal) => (
        <Proposal
          key={`${state.revision}:${proposal.id}`}
          proposal={proposal}
          busy={busy}
          store={store}
        />
      ))}
      {facts.length ? (
        <ul className="cands">
          {facts.map((f) => (
            <li key={f.id} className="cand">
              <span className="cand__name">{f.characteristic_name}</span>
              <span className="cand__code">
                {f.origin === "decision"
                  ? String(f.value)
                  : f.raw_unit && f.kind !== "interval"
                    ? `${f.raw_value} ${f.raw_unit}`
                    : f.raw_value}
              </span>
              <span className="cand__reason">
                {f.status === "proposed"
                  ? "предложение, не принято"
                  : f.status === "confirmed_by_user"
                    ? "подтверждено вами"
                    : f.status === "accepted_from_model"
                      ? "принято автоматически"
                      : f.status === "ambiguous"
                        ? "требует проверки"
                        : ORIGIN[f.origin]}
                {f.origin === "decision" && f.source && <span> · «{f.source.quote}»</span>}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">
          Пока нет. Здесь появятся значения из описания и ответов, приведённые к справочнику КТРУ.
        </p>
      )}
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
              {positions(compatible)}
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
                    {c.reason && <span className="cand__reason">{c.reason.text}</span>}
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
          <NextAction view={view} store={store} />
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
            <Characteristics state={state} busy={busy} store={store} />
            <Candidates state={state} />
          </aside>
        )}
      </div>
    </>
  );
}
