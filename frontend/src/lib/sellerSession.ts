// Сессия экрана поставщика без React: черновик ввода, отправка, восстановление по адресу и
// защита от устаревших ответов. Экран подписывается через `useSyncExternalStore`.
import {
  ApiError,
  NetworkError,
  type SellerApi,
  type SessionState,
  type FactMutation,
  type EnumAction,
} from "../api/types";

/** Предел бэкенда для текста сообщения, в символах. */
export const MAX_TEXT = 4000;

/** Сбой запроса или анализа — не «ничего не найдено». */
export type Failure = { title: string; text: string; details: string[] };

export type SellerView = {
  sessionId: string | null;
  state: SessionState | null;
  /** текст в поле ввода; очищается только после успешного анализа */
  draft: string;
  busy: boolean;
  failure: Failure | null;
};

const INITIAL: SellerView = {
  sessionId: null,
  state: null,
  draft: "",
  busy: false,
  failure: null,
};

export const textLength = (text: string) => [...text].length;

function failureOf(error: unknown): Failure {
  if (error instanceof NetworkError)
    return {
      title: "Нет связи с сервером",
      text: "Проверьте подключение и отправьте ещё раз — описание сохранено.",
      details: [],
    };
  if (error instanceof ApiError) {
    if (error.code === "session_not_found")
      return {
        title: "Сессия не найдена",
        text: "Отправьте описание ещё раз — начнётся новая карточка.",
        details: [],
      };
    if (error.code === "idempotency_conflict")
      return {
        title: "Запрос уже отправлялся с другим текстом",
        text: "Отправьте описание ещё раз.",
        details: [],
      };
    if (error.code === "invalid_fact_edit")
      return { title: "Правка не применена", text: error.message, details: [] };
    if (error.status === 422)
      return {
        title: "Сервер не принял данные",
        text:
          error.code === "option_not_found"
            ? error.message
            : `Проверьте введённые данные. Описание должно быть непустым и не длиннее ${MAX_TEXT} символов.`,
        details: [],
      };
    if (error.status >= 500)
      return {
        title: "Сервер не ответил",
        text: `Ошибка ${error.status}. Попробуйте ещё раз — описание сохранено.`,
        details: error.code ? [error.message] : [],
      };
    return { title: "Запрос не выполнен", text: error.message, details: [] };
  }
  return { title: "Что-то пошло не так", text: String(error), details: [] };
}

/** Сбой, после которого сервер мог успеть сохранить сообщение. */
const mayHaveReachedServer = (e: unknown) =>
  e instanceof NetworkError || (e instanceof ApiError && e.status >= 500);

function technicalFailure(state: SessionState): Failure {
  return {
    title: "Анализ не выполнен: технический сбой",
    text: "Это не значит, что товар не найден. Отправьте описание ещё раз.",
    details: state.errors.flatMap((e) => ("code" in e ? [e.message] : [])),
  };
}

export function createSellerSession(
  api: SellerApi,
  newKey: () => string = () => crypto.randomUUID(),
) {
  let view = INITIAL;
  const listeners = new Set<() => void>();
  // reset и open меняют эпоху: ответы прежней эпохи не трогают экран вовсе
  let epoch = 0;
  // номер запроса по порядку отправки; показан ответ с наибольшим номером
  let seq = 0;
  let applied = 0;
  let pending = 0;
  let session: Promise<string> | null = null;
  // тексты в пути: повторный Enter не создаёт лишнюю ревизию
  const inflight = new Set<string>();
  // ключ последней попытки: повтор того же текста после сбоя в пути идёт с ним же — если
  // сервер успел сохранить сообщение, он вернёт ту же ревизию, а не создаст дубль
  let retry: { text: string; key: string } | null = null;
  // ответ в пути: повторный клик по варианту не шлёт второй ответ на тот же вопрос
  let answering = false;

  const newEpoch = () => {
    epoch++;
    pending = 0;
    session = null;
    retry = null;
    answering = false;
    inflight.clear();
  };

  const set = (patch: Partial<SellerView>) => {
    view = { ...view, ...patch };
    for (const l of listeners) l();
  };

  const isOlder = (next: SessionState) =>
    view.state?.session_id === next.session_id && next.revision < view.state.revision;

  async function run(call: () => Promise<SessionState>, sent: string | null) {
    const mine = epoch;
    const n = ++seq;
    pending++;
    set({ busy: true, failure: null });
    let result: SessionState | null = null;
    let error: unknown = null;
    try {
      result = await call();
    } catch (e) {
      error = e;
    }
    if (mine !== epoch) return;
    pending--;
    const patch: Partial<SellerView> = { busy: pending > 0 };
    if (n > applied && !(result && isOlder(result))) {
      applied = n;
      if (result) {
        const failed = result.status === "technical_error";
        patch.state = result;
        patch.sessionId = result.session_id;
        patch.failure = failed ? technicalFailure(result) : null;
        if (!failed && sent !== null && view.draft.trim() === sent) patch.draft = "";
      } else {
        patch.failure = failureOf(error);
      }
    }
    set(patch);
  }

  function ensureSession(): Promise<string> {
    if (!session) {
      const mine = epoch;
      const created = api.create().then((s) => {
        if (mine === epoch && !view.sessionId) set({ sessionId: s.session_id });
        return s.session_id;
      });
      session = created;
      created.catch(() => {
        if (session === created) session = null;
      });
    }
    return session;
  }

  return {
    view: () => view,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => void listeners.delete(listener);
    },
    setDraft(draft: string) {
      set({ draft });
    },
    /** Отправить черновик; пустой не отправляется, слишком длинный — замечание без запроса. */
    submit(): Promise<void> {
      const text = view.draft.trim();
      if (!text) return Promise.resolve();
      if (textLength(text) > MAX_TEXT) {
        set({
          failure: {
            title: "Слишком длинное описание",
            text: `Сократите до ${MAX_TEXT} символов: сейчас ${textLength(text)}.`,
            details: [],
          },
        });
        return Promise.resolve();
      }
      if (inflight.has(text)) return Promise.resolve();
      const key = retry?.text === text ? retry.key : newKey();
      const attempt = { text, key };
      retry = attempt;
      const mine = epoch;
      inflight.add(text);
      return run(async () => {
        let lost = false;
        try {
          return await api.message(await ensureSession(), text, key);
        } catch (e) {
          lost = mayHaveReachedServer(e);
          if (mine === epoch && e instanceof ApiError && e.code === "session_not_found")
            session = null;
          throw e;
        } finally {
          if (mine === epoch) {
            inflight.delete(text);
            if (!lost && retry === attempt) retry = null;
          }
        }
      }, text);
    },
    /** Ответить на вопрос показанной ревизии; `null` — «не знаю». Черновик не трогается.
     *  Вопрос устарел (409 `stale_question`) — показываем сессию как она есть на сервере. */
    answer(optionId: string | null): Promise<void> {
      const state = view.state;
      const question = state?.next_question;
      if (!state || !question || answering) return Promise.resolve();
      answering = true;
      const mine = epoch;
      return run(async () => {
        try {
          return await api.answer(state.session_id, question.question_id, optionId);
        } catch (e) {
          if (e instanceof ApiError && e.code === "stale_question")
            return await api.get(state.session_id);
          throw e;
        } finally {
          if (mine === epoch) answering = false;
        }
      }, null);
    },
    async mutate(factId: string | null, body: FactMutation): Promise<boolean> {
      const state = view.state;
      if (!state || view.busy) return false;
      let saved = false;
      const mine = epoch;
      await run(async () => {
        try {
          const next = await api.mutate(state.session_id, factId, body);
          saved = true;
          return next;
        } catch (e) {
          if (e instanceof ApiError && e.code === "stale_revision") {
            const current = await api.get(state.session_id);
            if (mine === epoch && view.sessionId === state.session_id) set({ state: current });
          }
          throw e;
        }
      }, null);
      return mine === epoch && saved;
    },
    recalculate(): Promise<void> {
      const state = view.state;
      if (!state || view.busy) return Promise.resolve();
      return run(() => api.recalculate(state.session_id, state.revision), null);
    },
    resolveEnum(proposalId: string, action: EnumAction, values: string[] = []): Promise<void> {
      const state = view.state;
      if (!state || answering || view.busy) return Promise.resolve();
      answering = true;
      const mine = epoch;
      return run(async () => {
        try {
          return await api.resolveEnum(
            state.session_id,
            state.revision,
            proposalId,
            action,
            values,
          );
        } catch (e) {
          if (e instanceof ApiError && e.code === "stale_revision")
            return await api.get(state.session_id);
          if (e instanceof ApiError && e.status === 422)
            throw new ApiError(422, e.code, "Выберите допустимое сочетание значений из списка.");
          throw e;
        } finally {
          if (mine === epoch) answering = false;
        }
      }, null);
    },
    /** Восстановить сессию по идентификатору из адреса. */
    open(id: string): Promise<void> {
      newEpoch();
      const mine = epoch;
      session = Promise.resolve(id);
      set({ sessionId: id, state: view.state?.session_id === id ? view.state : null });
      return run(async () => {
        try {
          return await api.get(id);
        } catch (e) {
          if (mine === epoch && e instanceof ApiError && e.code === "session_not_found") {
            session = null;
            set({ sessionId: null });
          }
          throw e;
        }
      }, null);
    },
    reset() {
      newEpoch();
      set(INITIAL);
    },
  };
}

export type SellerSession = ReturnType<typeof createSellerSession>;
