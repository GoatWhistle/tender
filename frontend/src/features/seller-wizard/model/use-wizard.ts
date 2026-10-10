import { useCallback, useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import { useSearchParams } from "react-router-dom";
import { sellerApi } from "../../../api";
import type { FactMutation } from "../../../api/types";
import {
  createSellerSession,
  type SellerSession,
  type SellerView,
} from "../../../lib/sellerSession";
import { withViewTransition } from "../../../shared/motion";
import { reachableStep, STEPS, stepIndex } from "./steps";

export interface Wizard {
  readonly view: SellerView;
  readonly store: SellerSession;
  readonly step: number;
  readonly reachable: number;
  readonly goTo: (index: number) => void;
  readonly submit: () => Promise<void>;
  readonly answer: (optionId: string | null) => Promise<void>;
  readonly mutate: (factId: string | null, body: FactMutation) => Promise<boolean>;
  readonly restart: () => void;
}

export function useWizard(): Wizard {
  const store = useMemo(() => createSellerSession(sellerApi), []);
  const view = useSyncExternalStore(store.subscribe, store.view);
  const [params, setParams] = useSearchParams();
  const urlId = params.get("s");
  const step = stepIndex(params.get("step"));
  const reachable = reachableStep(view.state);
  const paramsRef = useRef(params);
  paramsRef.current = params;

  const write = useCallback(
    (patch: Record<string, string | null>, replace = false) => {
      const next = new URLSearchParams(paramsRef.current);
      for (const [k, v] of Object.entries(patch)) {
        if (v === null) next.delete(k);
        else next.set(k, v);
      }
      setParams(next, { replace });
    },
    [setParams],
  );

  useEffect(() => {
    const current = store.view().sessionId;
    if (urlId && urlId !== current) void store.open(urlId);
    if (!urlId && current) store.reset();
  }, [urlId, store]);

  useEffect(() => {
    const current = store.view().sessionId;
    if (current && current !== paramsRef.current.get("s")) write({ s: current }, true);
  }, [view.sessionId, store, write]);

  useEffect(() => {
    if (view.state && step > reachable) write({ step: STEPS[reachable] ?? null }, true);
  }, [view.state, step, reachable, write]);

  const goTo = useCallback(
    (index: number) =>
      withViewTransition(() => write({ step: index === 0 ? null : (STEPS[index] ?? null) })),
    [write],
  );

  const submit = useCallback(async () => {
    const before = store.view().state?.revision ?? -1;
    await store.submit();
    const after = store.view().state;
    if (after && after.revision !== before && after.path && after.status !== "technical_error")
      withViewTransition(() => write({ step: STEPS[1] }));
  }, [store, write]);

  const answer = useCallback(
    async (optionId: string | null) => {
      const hadPath = Boolean(store.view().state?.path);
      await store.answer(optionId);
      if (!hadPath && store.view().state?.path) withViewTransition(() => write({ step: STEPS[1] }));
    },
    [store, write],
  );

  const mutate = useCallback(
    async (factId: string | null, body: FactMutation) => {
      const ok = await store.mutate(factId, body);
      if (ok && store.view().state?.results_stale) await store.recalculate();
      return ok;
    },
    [store],
  );

  const restart = useCallback(() => {
    store.reset();
    setParams(new URLSearchParams());
  }, [store, setParams]);

  return { view, store, step, reachable, goTo, submit, answer, mutate, restart };
}
