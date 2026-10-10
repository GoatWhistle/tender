import { useState, type FormEvent } from "react";
import type { Fact, FactMutation, FactValue, SessionState } from "../api/types";
import type { SellerSession } from "../lib/sellerSession";

const label = (f: Fact) =>
  `${f.characteristic_name ?? "Без привязки"}${f.component ? ` (${f.component})` : ""}: ${f.raw_value}${f.raw_unit && f.kind !== "interval" ? ` ${f.raw_unit}` : ""}`;
const ACTIONS: Record<string, string> = {
  edit: "Правка",
  clarification: "Запрос уточнения",
  delete: "Удаление",
  confirm: "Подтверждение",
  restore: "Восстановление",
  split: "Разделение по частям",
  text_correction: "Исправление текстом",
  accept_suggestion: "Принятие предложения",
};
const componentKey = (f: Fact) => {
  const text = (f.component || f.characteristic_name || "").toLowerCase();
  return ["столешниц", "каркас", "ножк", "основан", "обивк"].find(stem => text.includes(stem)) ?? f.component ?? null;
};
const active = (f: Fact) => f.status !== "superseded" && f.status !== "deleted";

export function ValueFields({
  value,
  onChange,
}: {
  value: FactValue;
  onChange: (v: FactValue) => void;
}) {
  return (
    <div className="fact-fields">
      <label>
        Характеристика
        <input
          required
          value={value.characteristic_name}
          onChange={(e) => onChange({ ...value, characteristic_name: e.target.value })}
        />
      </label>
      <label>
        Часть товара
        <input
          value={value.component ?? ""}
          placeholder="Например, столешница"
          onChange={(e) => onChange({ ...value, component: e.target.value })}
        />
      </label>
      <label>
        Тип значения
        <select
          value={value.kind}
          onChange={(e) => onChange({ ...value, kind: e.target.value as FactValue["kind"] })}
        >
          <option value="text">Текст</option>
          <option value="number">Число</option>
          <option value="range">Диапазон</option>
        </select>
      </label>
      <label>
        Значение
        <input
          required
          value={value.raw_value}
          placeholder={value.kind === "range" ? "10..20" : ""}
          onChange={(e) => onChange({ ...value, raw_value: e.target.value })}
        />
      </label>
      <label>
        Единица
        <input
          value={value.raw_unit ?? ""}
          placeholder="мм, см, м…"
          onChange={(e) => onChange({ ...value, raw_unit: e.target.value || null })}
        />
      </label>
    </div>
  );
}

export const valueOf = (f: Fact): FactValue => ({
  characteristic_name: f.characteristic_name ?? "",
  raw_value: f.kind === "range" && Array.isArray(f.value) ? f.value.join("..") : f.raw_value,
  raw_unit: f.raw_unit,
  kind: f.kind === "interval" ? "range" : f.kind,
  component: f.component,
});

export function FactForm({
  state,
  store,
  fact,
  related = [],
  initial,
  diagnosticIndex,
  onClose,
}: {
  state: SessionState;
  store: SellerSession;
  fact: Fact | null;
  related?: Fact[];
  initial?: FactValue;
  diagnosticIndex?: number;
  onClose: () => void;
}) {
  const [value, setValue] = useState<FactValue>(
    initial ?? (fact ? valueOf(fact) : { characteristic_name: "", raw_value: "", kind: "text" }),
  );
  const [revision, setRevision] = useState(state.revision);
  const [targetId, setTargetId] = useState(fact?.id ?? null);
  const [split, setSplit] = useState(false);
  const [bindings, setBindings] = useState(() =>
    [fact, ...related].filter((f): f is Fact => !!f).map(valueOf),
  );
  const changed = revision !== state.revision;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const body: FactMutation = {
      ...value,
      expected_revision: revision,
      action: split ? "split" : diagnosticIndex === undefined ? "edit" : "accept_suggestion",
      related_ids: related.map((f) => f.id),
      bindings: split ? bindings : undefined,
      diagnostic_index: diagnosticIndex,
    };
    if (await store.mutate(targetId, body)) onClose();
  };
  return (
    <form className="fact-editor" onSubmit={(e) => void submit(e)} aria-label="Редактор факта">
      <h3>{diagnosticIndex === undefined ? "Изменить характеристику" : "Принять исправление"}</h3>
      {changed && (
        <div role="alert">
          <p>Сессия изменилась. Ваш ввод сохранён. Сравните с актуальными значениями:</p>
          <ul>
            {state.facts.filter(active).map((f) => (
              <li key={f.id}>{label(f)}</li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => {
              let current = state.facts.find((f) => f.id === targetId);
              const seen = new Set<string>();
              while (current?.superseded_by && !seen.has(current.id)) {
                seen.add(current.id);
                current = state.facts.find((f) => f.id === current?.superseded_by);
              }
              setTargetId(current && active(current) ? current.id : null);
              setRevision(state.revision);
            }}
            disabled={diagnosticIndex !== undefined || related.length > 0}
          >
            Сравнил, использовать текущую ревизию
          </button>
        </div>
      )}
      {changed && (diagnosticIndex !== undefined || related.length > 0) && (
        <p>Заново откройте актуальное предложение или конфликт. Старое действие не повторяется.</p>
      )}
      {related.length > 0 && (
        <label>
          <input type="checkbox" checked={split} onChange={(e) => setSplit(e.target.checked)} />
          Значения относятся к разным частям товара
        </label>
      )}
      {split ? (
        bindings.map((v, i) => (
          <fieldset key={i}>
            <legend>Утверждение {i + 1}</legend>
            <ValueFields
              value={v}
              onChange={(next) => setBindings(bindings.map((b, j) => (i === j ? next : b)))}
            />
          </fieldset>
        ))
      ) : (
        <ValueFields value={value} onChange={setValue} />
      )}
      {diagnosticIndex !== undefined && (
        <p>
          Проверьте значение, единицу и привязку. Изменение применяется только после подтверждения.
        </p>
      )}
      <div className="fact-actions">
        <button disabled={changed || store.view().busy} className="example">
          {diagnosticIndex === undefined ? "Сохранить" : "Подтвердить исправление"}
        </button>
        <button type="button" className="textlink" onClick={onClose}>
          Отмена
        </button>
      </div>
    </form>
  );
}

export function EditableFacts({ state, store }: { state: SessionState; store: SellerSession }) {
  const [editing, setEditing] = useState<{ fact: Fact; related: Fact[] } | null>(null);
  const facts = state.facts.filter(active);
  const busy = store.view().busy;
  const mutate = (fact: Fact, action: FactMutation["action"], related: Fact[] = []) =>
    void store.mutate(fact.id, {
      action,
      expected_revision: state.revision,
      related_ids: related.map((f) => f.id),
    });
  return (
    <section aria-labelledby="facts-title">
      <h2 id="facts-title" className="block-title">
        Характеристики
      </h2>
      {editing && (
        <FactForm
          key={editing.fact.id}
          state={state}
          store={store}
          {...editing}
          onClose={() => setEditing(null)}
        />
      )}
      {facts.length === 0 && <p className="muted">Пока нет характеристик.</p>}
      <ul className="cands">
        {facts.map((f) => {
          const related =
            f.status === "ambiguous"
              ? facts.filter(
                  (x) =>
                    x.id !== f.id &&
                    x.status === "ambiguous" &&
                    x.characteristic_name === f.characteristic_name &&
                    componentKey(x) === componentKey(f),
                )
              : [];
          return (
            <li key={f.id} className="cand">
              <span className="cand__name">{label(f)}</span>
              <span className="cand__reason">
                {f.status === "ambiguous"
                  ? "Требует уточнения"
                  : f.origin === "catalog"
                    ? "Из справочника"
                    : f.origin === "user"
                      ? "Подтверждено вами"
                      : "Из описания"}
              </span>
              <div className="fact-actions">
                <button
                  type="button"
                  className="textlink"
                  disabled={busy}
                  onClick={() => setEditing({ fact: f, related })}
                >
                  Изменить
                </button>
                <button
                  type="button"
                  className="textlink"
                  disabled={busy}
                  onClick={() => mutate(f, "confirm", related)}
                >
                  {related.length ? "Оставить это значение" : "Подтвердить"}
                </button>
                <button
                  type="button"
                  className="textlink"
                  disabled={busy}
                  onClick={() => mutate(f, "delete")}
                >
                  Удалить
                </button>
                {related.length > 0 && (
                  <button
                    type="button"
                    className="textlink"
                    disabled={busy}
                    onClick={() => mutate(f, "delete", related)}
                  >
                    Удалить спорные значения
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      {(state.fact_history?.length ?? 0) > 0 && (
        <details className="fact-history">
          <summary>История изменений ({state.fact_history?.length})</summary>
          <ol>
            {state.fact_history?.map((event, i) => (
              <li key={i}>
                <strong>{ACTIONS[event.action] ?? event.action}</strong> ·{" "}
                <time>{new Date(event.created_at).toLocaleString("ru")}</time>
                {event.before.map((f) => (
                  <div key={f.id}>
                    <p>
                      Было: {label(f)} ·{" "}
                      {f.origin === "parser"
                        ? "из описания"
                        : f.origin === "catalog"
                          ? "из справочника"
                          : "ввод пользователя"}
                    </p>
                    {f.source && <blockquote>{f.source.quote}</blockquote>}
                    <button
                      type="button"
                      className="textlink"
                      disabled={busy}
                      onClick={() => mutate(f, "restore")}
                    >
                      Восстановить: {f.raw_value}
                    </button>
                  </div>
                ))}
                {event.after.map((f) => (
                  <p key={f.id}>Стало: {label(f)}</p>
                ))}
                {event.after.length === 0 && <p>Факт удалён и не применяется.</p>}
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  );
}
