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
});
