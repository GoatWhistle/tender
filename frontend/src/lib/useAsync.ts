import { useEffect, useState } from "react";

export type AsyncState<T> =
  | { status: "loading"; data?: T }
  | { status: "ok"; data: T }
  | { status: "error"; error: Error; data?: T };

/** Загрузка с отбрасыванием устаревших ответов; пока идёт новый запрос, держит прежние данные. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });
  useEffect(() => {
    let live = true;
    setState((s) => ({ status: "loading", data: s.data }));
    load().then(
      (data) => live && setState({ status: "ok", data }),
      (error: Error) => live && setState((s) => ({ status: "error", error, data: s.data })),
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
