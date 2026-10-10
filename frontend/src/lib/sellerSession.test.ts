import { describe, expect, it, vi } from "vitest";
import { ApiError, NetworkError, type SellerApi, type SessionState } from "../api/types";
import { MAX_TEXT, createSellerSession } from "./sellerSession";

function state(patch: Partial<SessionState> = {}): SessionState {
  return {
    session_id: "s1",
    revision: 0,
    status: "draft",
    messages: [],
    path: null,
    alternatives: [],
    candidates: [],
    candidate_counts: { in_group: 0, compatible: 0, excluded_by_rules: 0 },
    facts: [],
    errors: [],
    warnings: [],
    next_question: null,
    dialog: [],
    card_complete: false,
    missing_required: [],
    common_fields: [],
    unanswered: [],
    unsupported_rules: [],
    ...patch,
  };
}

function resolved(revision: number, group: string): SessionState {
  return state({
    revision,
    status: "needs_clarification",
    path: { category: "Мебель", group: { code: group, name: group }, positions: 2 },
  });
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function fakeApi(overrides: Partial<SellerApi> = {}) {
  return {
    create: vi.fn<SellerApi["create"]>(async () => state()),
    get: vi.fn<SellerApi["get"]>(async (id) => state({ session_id: id })),
    message: vi.fn<SellerApi["message"]>(async () => resolved(1, "A")),
    answer: vi.fn<SellerApi["answer"]>(async () => resolved(3, "A")),
    mutate: vi.fn<SellerApi["mutate"]>(async () => resolved(4, "A")),
    recalculate: vi.fn<SellerApi["recalculate"]>(async () => resolved(4, "A")),
    ...overrides,
  };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

let keys = 0;
const newKey = () => `key-${++keys}`;

describe("createSellerSession", () => {
  it("создаёт сессию, отправляет текст сообщением и очищает поле", async () => {
    const api = fakeApi();
    const s = createSellerSession(api, newKey);
    s.setDraft("  Шкаф для одежды  ");
    await s.submit();
    expect(api.create).toHaveBeenCalledOnce();
    expect(api.message).toHaveBeenCalledWith("s1", "Шкаф для одежды", expect.any(String));
    expect(s.view()).toMatchObject({ sessionId: "s1", draft: "", busy: false, failure: null });
    expect(s.view().state?.path?.group.code).toBe("A");
  });

  it("после успешного ответа следующая отправка — с новым Idempotency-Key", async () => {
    const api = fakeApi();
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    await s.submit();
    s.setDraft("Шкаф");
    await s.submit();
    const [k1, k2] = vi.mocked(api.message).mock.calls.map((c) => c[2]);
    expect(k1).toBeTruthy();
    expect(k1).not.toBe(k2);
  });

  it.each([
    ["сетевого сбоя", new NetworkError("Failed to fetch")],
    ["504 прокси", new ApiError(504, null, "504 Gateway Timeout")],
  ])("повтор того же текста после %s — с тем же ключом", async (_, error) => {
    const api = fakeApi({
      message: vi.fn<SellerApi["message"]>().mockRejectedValueOnce(error),
    });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    await s.submit();
    await s.submit();
    s.setDraft("Шкаф металлический");
    await s.submit();
    const [k1, k2, k3] = vi.mocked(api.message).mock.calls.map((c) => c[2]);
    expect(k2).toBe(k1);
    expect(k3).not.toBe(k1);
  });

  it.each([
    ["technical_error", () => Promise.resolve(state({ revision: 1, status: "technical_error" }))],
    ["409", () => Promise.reject(new ApiError(409, "idempotency_conflict", "Конфликт"))],
  ])("после %s повтор идёт с новым ключом", async (_, first) => {
    const api = fakeApi({ message: vi.fn<SellerApi["message"]>().mockImplementationOnce(first) });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    await s.submit();
    await s.submit();
    const [k1, k2] = vi.mocked(api.message).mock.calls.map((c) => c[2]);
    expect(k2).not.toBe(k1);
  });

  it("пустой и слишком длинный текст не отправляет", async () => {
    const api = fakeApi();
    const s = createSellerSession(api, newKey);
    s.setDraft("   \n ");
    await s.submit();
    expect(s.view().failure).toBeNull();
    s.setDraft("ы".repeat(MAX_TEXT + 1));
    await s.submit();
    expect(api.create).not.toHaveBeenCalled();
    expect(api.message).not.toHaveBeenCalled();
    expect(s.view().failure?.title).toMatch(/длинн/i);
    expect(s.view().draft).toHaveLength(MAX_TEXT + 1);
  });

  it("ответ первого запроса, пришедший после второго, не перетирает результат", async () => {
    const first = deferred<SessionState>();
    const second = deferred<SessionState>();
    const api = fakeApi({
      message: vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise),
    });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    const a = s.submit();
    await flush();
    s.setDraft("Шкаф металлический");
    const b = s.submit();
    await flush();
    expect(api.create).toHaveBeenCalledOnce();

    second.resolve(resolved(2, "B"));
    await b;
    first.resolve(resolved(1, "A"));
    await a;

    expect(s.view().state?.path?.group.code).toBe("B");
    expect(s.view().busy).toBe(false);
  });

  it("сбой старого запроса после успеха нового не показывается", async () => {
    const first = deferred<SessionState>();
    const api = fakeApi({
      message: vi.fn().mockReturnValueOnce(first.promise).mockResolvedValueOnce(resolved(2, "B")),
    });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    const a = s.submit();
    await flush();
    s.setDraft("Шкаф металлический");
    await s.submit();
    first.reject(new NetworkError("Failed to fetch"));
    await a;
    expect(s.view().failure).toBeNull();
    expect(s.view().state?.path?.group.code).toBe("B");
  });

  it("тот же текст, пока он в пути, второй раз не отправляет", async () => {
    const pending = deferred<SessionState>();
    const api = fakeApi({ message: vi.fn(() => pending.promise) });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    const a = s.submit();
    await s.submit();
    await flush();
    pending.resolve(resolved(1, "A"));
    await a;
    expect(api.message).toHaveBeenCalledOnce();
  });

  it("снимок с меньшей ревизией той же сессии игнорирует", async () => {
    const api = fakeApi({
      message: vi.fn().mockResolvedValueOnce(resolved(3, "B")),
      get: vi.fn(async () => resolved(2, "A")),
    });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    await s.submit();
    await s.open("s1");
    expect(s.view().state?.revision).toBe(3);
  });

  it("technical_error — сбой с текстом бэкенда, ввод сохранён", async () => {
    const api = fakeApi({
      message: vi.fn(async () =>
        state({
          revision: 1,
          status: "technical_error",
          errors: [{ code: "model_failure", message: "Модель поиска недоступна" }],
        }),
      ),
    });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф для одежды");
    await s.submit();
    const v = s.view();
    expect(v.draft).toBe("Шкаф для одежды");
    expect(v.failure?.details).toEqual(["Модель поиска недоступна"]);
    expect(v.state?.status).toBe("technical_error");
  });

  it("сетевой сбой — сбой, ввод сохранён, состояние прежнее", async () => {
    const api = fakeApi({
      message: vi
        .fn()
        .mockResolvedValueOnce(resolved(1, "A"))
        .mockRejectedValueOnce(new NetworkError("Failed to fetch")),
    });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    await s.submit();
    s.setDraft("глубина 60 см");
    await s.submit();
    const v = s.view();
    expect(v.draft).toBe("глубина 60 см");
    expect(v.failure?.title).toMatch(/связ/i);
    expect(v.state?.path?.group.code).toBe("A");
    expect(v.busy).toBe(false);
  });

  it.each([
    [new ApiError(404, "session_not_found", "Сессия не найдена"), /не найдена/],
    [new ApiError(409, "idempotency_conflict", "Конфликт"), /уже отправ/],
    [new ApiError(422, null, "422 Unprocessable Entity"), /не принял/],
    [new ApiError(503, "model_failure", "Модель недоступна"), /сервер/i],
  ])("ошибку API %o показывает как сбой", async (error, title) => {
    const api = fakeApi({ message: vi.fn().mockRejectedValue(error) });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    await s.submit();
    expect(s.view().failure?.title).toMatch(title);
    expect(s.view().draft).toBe("Шкаф");
  });

  it("сбой создания сессии не оставляет её: повтор создаёт заново", async () => {
    const api = fakeApi({
      create: vi
        .fn()
        .mockRejectedValueOnce(new NetworkError("Failed to fetch"))
        .mockResolvedValueOnce(state()),
    });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    await s.submit();
    expect(s.view().failure).not.toBeNull();
    await s.submit();
    expect(api.create).toHaveBeenCalledTimes(2);
    expect(s.view().failure).toBeNull();
  });

  it("open восстанавливает сессию из адреса, reset отбрасывает ответы в пути", async () => {
    const pending = deferred<SessionState>();
    const api = fakeApi({ get: vi.fn(() => pending.promise) });
    const s = createSellerSession(api, newKey);
    const opening = s.open("s9");
    expect(s.view().sessionId).toBe("s9");
    s.reset();
    pending.resolve(resolved(1, "A"));
    await opening;
    expect(s.view()).toMatchObject({ sessionId: null, state: null, busy: false });
  });

  it("сессия из адреса не найдена — первая же отправка создаёт новую", async () => {
    const api = fakeApi({
      get: vi.fn<SellerApi["get"]>(async () => {
        throw new ApiError(404, "session_not_found", "Сессия не найдена");
      }),
    });
    const s = createSellerSession(api, newKey);
    await s.open("dead");
    expect(s.view()).toMatchObject({ sessionId: null, state: null });
    expect(s.view().failure?.title).toMatch(/не найдена/);
    s.setDraft("Шкаф");
    await s.submit();
    expect(api.create).toHaveBeenCalledOnce();
    expect(api.message).toHaveBeenCalledWith("s1", "Шкаф", expect.any(String));
  });

  it("ответ прежней сессии после перехода по адресу к другой не показывается", async () => {
    const inFlight = deferred<SessionState>();
    const api = fakeApi({
      message: vi.fn<SellerApi["message"]>(() => inFlight.promise),
      get: vi.fn<SellerApi["get"]>(async (id) => ({ ...resolved(1, id), session_id: id })),
    });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    const a = s.submit();
    await flush();
    const opening = s.open("B");
    inFlight.resolve({ ...resolved(1, "A"), session_id: "s1" });
    await a;
    await opening;
    expect(s.view().sessionId).toBe("B");
    expect(s.view().state?.path?.group.code).toBe("B");
  });

  it("запрос прежней карточки после reset не снимает защиту от повтора в новой", async () => {
    const old = deferred<SessionState>();
    const fresh = deferred<SessionState>();
    const api = fakeApi({
      message: vi
        .fn<SellerApi["message"]>()
        .mockReturnValueOnce(old.promise)
        .mockReturnValueOnce(fresh.promise),
    });
    const s = createSellerSession(api, newKey);
    s.setDraft("Шкаф");
    const a = s.submit();
    await flush();
    s.reset();
    s.setDraft("Шкаф");
    const b = s.submit();
    await flush();
    old.resolve(resolved(1, "A"));
    await a;
    await s.submit();
    expect(api.message).toHaveBeenCalledTimes(2);
    fresh.resolve(resolved(1, "B"));
    await b;
  });

  it("уведомляет подписчиков", async () => {
    const s = createSellerSession(fakeApi(), newKey);
    const listener = vi.fn();
    const off = s.subscribe(listener);
    s.setDraft("Шкаф");
    expect(listener).toHaveBeenCalled();
    off();
    listener.mockClear();
    s.setDraft("Стол");
    expect(listener).not.toHaveBeenCalled();
  });

  describe("ответ на вопрос", () => {
    const question = {
      question_id: "q1",
      kind: "discriminate" as const,
      characteristic: "Материал",
      text: "Какое значение «Материал» у товара?",
      options: [{ id: "o1", label: "ДСП" }],
      allow_unknown: true,
    };
    const asked = state({ revision: 1, status: "needs_clarification", next_question: question });

    async function opened(api: ReturnType<typeof fakeApi>) {
      vi.mocked(api.get).mockResolvedValueOnce(asked);
      const s = createSellerSession(api, newKey);
      await s.open("s1");
      return s;
    }

    it("отправляет вариант или «не знаю» на вопрос текущей ревизии", async () => {
      const api = fakeApi();
      const s = await opened(api);
      const next = { ...question, question_id: "q2" };
      vi.mocked(api.answer).mockResolvedValueOnce({ ...asked, revision: 2, next_question: next });
      s.setDraft("недописанное");
      await s.answer("o1");
      expect(api.answer).toHaveBeenCalledWith("s1", "q1", "o1");
      expect(s.view()).toMatchObject({ busy: false, failure: null, draft: "недописанное" });
      expect(s.view().state?.next_question).toEqual(next);
      await s.answer(null);
      expect(api.answer).toHaveBeenLastCalledWith("s1", "q2", null);
      expect(s.view().state?.revision).toBe(3);
    });

    it("без вопроса ничего не отправляет", async () => {
      const api = fakeApi();
      const s = createSellerSession(api, newKey);
      await s.answer("o1");
      expect(api.answer).not.toHaveBeenCalled();
    });

    it("на устаревший вопрос перечитывает сессию без ошибки", async () => {
      const fresh = state({ revision: 4, status: "resolved" });
      const api = fakeApi({
        answer: vi.fn<SellerApi["answer"]>(async () => {
          throw new ApiError(409, "stale_question", "Вопрос устарел");
        }),
      });
      const s = await opened(api);
      vi.mocked(api.get).mockResolvedValueOnce(fresh);
      await s.answer("o1");
      expect(api.get).toHaveBeenLastCalledWith("s1");
      expect(s.view()).toMatchObject({ state: fresh, failure: null, busy: false });
    });

    it("сбой ответа показывается как сбой, вопрос остаётся", async () => {
      const api = fakeApi({
        answer: vi.fn<SellerApi["answer"]>(async () => {
          throw new NetworkError("Failed to fetch");
        }),
      });
      const s = await opened(api);
      await s.answer("o1");
      expect(s.view().failure?.title).toBe("Нет связи с сервером");
      expect(s.view().state).toBe(asked);
    });

    it("повторный клик во время ответа не отправляет второй запрос", async () => {
      const pending = deferred<SessionState>();
      const api = fakeApi({ answer: vi.fn<SellerApi["answer"]>(() => pending.promise) });
      const s = await opened(api);
      const first = s.answer("o1");
      void s.answer("o1");
      pending.resolve(resolved(2, "A"));
      await first;
      expect(api.answer).toHaveBeenCalledOnce();
    });
  });
});

it("диагностика характеристики не превращает успешный анализ в технический сбой", async () => {
  const diagnostic: import("../api/types").Diagnostic = {
    kind: "typo",
    fact_id: null,
    source_quote: "дреево",
    source: { message_id: "m1", quote: "дреево", start: 8, end: 14 },
    expected: [],
    suggestion: "дерево",
    candidates: ["дерево"],
    rule_ref: [],
    scope: { group_code: null, position_codes: [], complete: false },
    requires_confirmation: true,
    explanation: "Орфографическая гипотеза",
    alias_source: null,
  };
  const response = state({ revision: 1, status: "needs_clarification", errors: [diagnostic] });
  const api = fakeApi({ message: vi.fn().mockResolvedValue(response) });
  const store = createSellerSession(api, newKey);
  store.setDraft("Стол из дреево");
  await store.submit();
  expect(store.view().failure).toBeNull();
  expect(store.view().state?.errors).toEqual([diagnostic]);
  expect(api.answer).not.toHaveBeenCalled();
  const failed = state({
    status: "technical_error",
    errors: [diagnostic, { code: "model_failure", message: "Поиск недоступен" }],
  });
  const failedStore = createSellerSession(fakeApi({ get: async () => failed }), newKey);
  await failedStore.open("s1");
  expect(failedStore.view().failure?.details).toEqual(["Поиск недоступен"]);
});

it("сохраняет черновик и обновляет ревизию после конфликта правки без повтора", async () => {
  const api = fakeApi({
    get: vi
      .fn()
      .mockResolvedValueOnce(state({ revision: 1 }))
      .mockResolvedValueOnce(state({ revision: 2 })),
    mutate: vi.fn().mockRejectedValue(new ApiError(409, "stale_revision", "Сессия изменилась")),
  });
  const store = createSellerSession(api);
  await store.open("s1");
  store.setDraft("несохранённое описание");
  expect(await store.mutate("f1", { expected_revision: 1, action: "delete" })).toBe(false);
  expect(store.view().draft).toBe("несохранённое описание");
  expect(store.view().state?.revision).toBe(2);
  expect(store.view().failure?.text).toContain("Сессия изменилась");
  expect(api.mutate).toHaveBeenCalledTimes(1);
});
