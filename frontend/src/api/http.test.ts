import { afterEach, describe, expect, it, vi } from "vitest";
import { sellerApi } from "./http";
import { ApiError, NetworkError } from "./types";

function respond(status: number, body: unknown) {
  return vi.fn<typeof fetch>(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("sellerApi", () => {
  it("создаёт сессию без тела", async () => {
    const fetch = respond(200, { session_id: "s1" });
    vi.stubGlobal("fetch", fetch);
    await sellerApi.create();
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/v1/sessions");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeUndefined();
  });

  it("отправляет сообщение с Idempotency-Key", async () => {
    const fetch = respond(200, { session_id: "s1" });
    vi.stubGlobal("fetch", fetch);
    await sellerApi.message("s1", "Шкаф", "key-1");
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/v1/sessions/s1/messages");
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBe("key-1");
    expect(JSON.parse(String(init?.body))).toEqual({ text: "Шкаф" });
  });

  it("доменную ошибку отдаёт с кодом и текстом бэкенда", async () => {
    vi.stubGlobal(
      "fetch",
      respond(404, { code: "session_not_found", message: "Сессия не найдена" }),
    );
    const error = await sellerApi.get("nope").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, code: "session_not_found" });
    expect((error as ApiError).message).toBe("Сессия не найдена");
  });

  it("ответ без тела ошибки — ApiError без кода", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("Bad Gateway", { status: 502 })),
    );
    const error = await sellerApi.get("s1").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 502, code: null });
  });

  it("сетевой сбой — NetworkError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    await expect(sellerApi.get("s1")).rejects.toBeInstanceOf(NetworkError);
  });
});
