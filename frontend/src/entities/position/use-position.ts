import { useEffect, useState } from "react";
import { fetchPosition, type PositionDetail } from "./position";

type PositionState = {
  readonly code: string | null;
  readonly data: PositionDetail | null;
  readonly failed: boolean;
};

const cache = new Map<string, PositionDetail>();

export function usePosition(code: string | null): PositionState {
  const [state, setState] = useState<PositionState>(() => ({
    code,
    data: code ? (cache.get(code) ?? null) : null,
    failed: false,
  }));

  useEffect(() => {
    if (!code) return;
    const cached = cache.get(code);
    if (cached) {
      setState({ code, data: cached, failed: false });
      return;
    }
    const controller = new AbortController();
    setState((s) => ({ code, data: s.code === code ? s.data : null, failed: false }));
    fetchPosition(code, controller.signal)
      .then((data) => {
        cache.set(code, data);
        setState({ code, data, failed: false });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ code, data: null, failed: true });
      });
    return () => controller.abort();
  }, [code]);

  return state.code === code ? state : { code, data: null, failed: false };
}
