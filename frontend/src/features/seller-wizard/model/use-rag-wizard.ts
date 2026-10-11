import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ApiError,
  ragApi,
  type Extra,
  type Outcome,
  type Search,
  type Session,
  type Suggestion,
  type Verdict,
} from "../../../entities/rag";
import { t, type MessageKey } from "../../../shared/i18n";
import { withViewTransition } from "../../../shared/motion";

export const MAX_TEXT = 4000;

export type Operation =
  | "checking"
  | "searching"
  | "ranking"
  | "selecting"
  | "answering"
  | "updating"
  | "validating"
  | "suggesting"
  | "saving"
  | "loading";

export interface Failure {
  readonly title: string;
  readonly text: string;
}

export interface RagWizard {
  readonly search: Search | null;
  readonly session: Session | null;
  readonly draft: string;
  readonly operation: Operation | null;
  readonly busy: boolean;
  readonly failure: Failure | null;
  readonly verdict: Verdict | null;
  readonly suggestions: readonly Suggestion[] | null;
  readonly outcome: Outcome | null;
  readonly automatic: boolean;
  readonly step: number;
  readonly reachable: number;
  readonly setDraft: (value: string) => void;
  readonly goTo: (step: number) => void;
  readonly submit: () => void;
  readonly confirm: () => void;
  readonly choose: (code: string, automatic?: boolean) => void;
  readonly toGroups: () => void;
  readonly switchGroup: (code: string) => void;
  readonly answer: (body: { option: number } | { text: string }) => void;
  readonly pick: (code: string) => void;
  readonly values: (name: string, selected: readonly string[]) => void;
  readonly number: (name: string, value: number | null) => void;
  readonly describe: (text: string, name: string | null, done?: () => void) => void;
  readonly message: (text: string, done?: () => void) => void;
  readonly addExtra: (extra: Extra, done?: () => void) => void;
  readonly removeExtra: (index: number) => void;
  readonly suggest: () => void;
  readonly finish: (onDone?: (id: string) => void) => void;
  readonly retry: () => void;
  readonly restart: () => void;
}

export const OPERATION_LABEL: Record<Operation, MessageKey> = {
  checking: "seller:busy.checking",
  searching: "seller:busy.searching",
  ranking: "seller:busy.ranking",
  selecting: "seller:busy.selecting",
  answering: "seller:busy.answering",
  updating: "seller:busy.updating",
  validating: "seller:busy.validating",
  suggesting: "seller:busy.suggesting",
  saving: "seller:busy.saving",
  loading: "seller:busy.loading",
};

function failureOf(error: unknown): Failure {
  if (error instanceof ApiError) {
    if (error.status === 503 || error.code === "index_not_ready")
      return { title: t("errors:rag.unavailable"), text: error.message };
    if (error.status === 404) return { title: t("errors:rag.notFound"), text: error.message };
    if (error.status === 0)
      return { title: t("errors:rag.network"), text: t("errors:rag.networkText") };
    return { title: t("errors:rag.failed"), text: error.message };
  }
  return { title: t("errors:rag.failed"), text: String(error) };
}

function derivedStep(search: Search | null, session: Session | null, preview: boolean): number {
  if (session) {
    if (session.stage === "done" || preview) return 3;
    if (session.stage === "spec") return 2;
    return 1;
  }
  if (search && search.stage !== "review") return 1;
  return 0;
}

export function useRagWizard(): RagWizard {
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState<Search | null>(null);
  const [session, setSessionState] = useState<Session | null>(null);
  const [draft, setDraft] = useState(() => params.get("q") ?? "");
  const [operation, setOperation] = useState<Operation | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [suggestions, setSuggestions] = useState<readonly Suggestion[] | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [automatic, setAutomatic] = useState(true);
  const [preview, setPreview] = useState(false);
  const [manual, setManual] = useState<number | null>(null);
  const pending = useRef(false);
  const last = useRef<{ op: Operation; action: () => Promise<void> } | null>(null);
  const autoChosen = useRef<string | null>(null);
  const restored = useRef(false);
  const autostarted = useRef(false);

  const setSession = useCallback(
    (next: Session | null) => {
      setSessionState(next);
      setParams(
        (current) => {
          const copy = new URLSearchParams(current);
          copy.delete("q");
          if (next) copy.set("s", next.id);
          else copy.delete("s");
          return copy;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  const run = useCallback((op: Operation, action: () => Promise<void>) => {
    if (pending.current) return;
    pending.current = true;
    last.current = { op, action };
    setOperation(op);
    setFailure(null);
    action()
      .then(() => setManual(null))
      .catch((error: unknown) => setFailure(failureOf(error)))
      .finally(() => {
        pending.current = false;
        setOperation(null);
      });
  }, []);

  useEffect(() => {
    if (restored.current) return;
    restored.current = true;
    const id = params.get("s");
    if (!id || session) return;
    run("loading", async () => {
      setSession(await ragApi.session(id));
    });
  }, [params, run, session, setSession]);

  const retrieve = useCallback(async (value: Search) => {
    setOperation("searching");
    const found = await ragApi.candidates(value.id);
    setSearch(found);
    setOperation("ranking");
    const ranked = await ragApi.rerank(value.id);
    withViewTransition(() => setSearch(ranked));
  }, []);

  const submit = useCallback(() => {
    const text = draft.trim();
    if (!text || text.length > MAX_TEXT) return;
    run("checking", async () => {
      setAutomatic(true);
      setSession(null);
      setOutcome(null);
      setVerdict(null);
      setSuggestions(null);
      setPreview(false);
      autoChosen.current = null;
      const value = await ragApi.startSearch(text);
      setSearch(value);
      if (!value.fixes.length && !value.issues.length) await retrieve(value);
    });
  }, [draft, retrieve, run, setSession]);

  useEffect(() => {
    if (autostarted.current || !params.get("q") || params.get("s")) return;
    autostarted.current = true;
    submit();
  }, [params, submit]);

  const confirm = useCallback(() => {
    if (!search) return;
    if (draft.trim() !== search.description) {
      submit();
      return;
    }
    setDraft(search.corrected);
    run("searching", () => retrieve(search));
  }, [draft, retrieve, run, search, submit]);

  const choose = useCallback(
    (code: string, auto = false) => {
      if (!search) return;
      run("selecting", async () => {
        const next = await ragApi.select(search.id, code, auto);
        setVerdict(null);
        setSuggestions(null);
        setPreview(false);
        withViewTransition(() => setSession(next));
      });
    },
    [run, search, setSession],
  );

  useEffect(() => {
    if (!search || session || !automatic || search.stage !== "ranked") return;
    const code = search.auto_select_code;
    if (!code || autoChosen.current === search.id) return;
    autoChosen.current = search.id;
    const timer = window.setTimeout(() => choose(code, true), 900);
    return () => window.clearTimeout(timer);
  }, [automatic, choose, search, session]);

  const withSession = useCallback(
    (op: Operation, call: (id: string) => Promise<Session>, done?: () => void) => {
      if (!session) return;
      run(op, async () => {
        const next = await call(session.id);
        setSession(next);
        if (next.stage !== "done") setOutcome(null);
        done?.();
      });
    },
    [run, session, setSession],
  );

  const reachable = session
    ? session.stage === "spec" || session.stage === "done"
      ? 3
      : 1
    : search && search.stage !== "review"
      ? 1
      : 0;
  const step = manual ?? derivedStep(search, session, preview);

  return {
    search,
    session,
    draft,
    operation,
    busy: operation !== null,
    failure,
    verdict,
    suggestions,
    outcome,
    automatic,
    step,
    reachable,
    setDraft,
    goTo: (target) => {
      if (target > reachable) return;
      withViewTransition(() => {
        if (target === 3) {
          setPreview(true);
          setManual(null);
          return;
        }
        setPreview(false);
        setManual(target === derivedStep(search, session, false) ? null : target);
      });
    },
    submit,
    confirm,
    choose,
    toGroups: () => {
      setAutomatic(false);
      setOutcome(null);
      setVerdict(null);
      setSuggestions(null);
      setPreview(false);
      setManual(null);
      withViewTransition(() => setSession(null));
    },
    switchGroup: (code) => withSession("selecting", (id) => ragApi.group(id, code)),
    answer: (body) => withSession("answering", (id) => ragApi.answer(id, body)),
    pick: (code) => withSession("selecting", (id) => ragApi.pick(id, code)),
    values: (name, selected) => withSession("updating", (id) => ragApi.values(id, name, selected)),
    number: (name, value) => withSession("updating", (id) => ragApi.number(id, name, value)),
    describe: (text, name, done) =>
      withSession("answering", (id) => ragApi.describe(id, text, name), done),
    message: (text, done) => withSession("answering", (id) => ragApi.message(id, text), done),
    addExtra: (extra, done) => {
      if (!session) return;
      run("validating", async () => {
        const response = await ragApi.addExtra(session.id, extra);
        setVerdict(response);
        setSession(response.session);
        if (response.accepted) done?.();
      });
    },
    removeExtra: (index) => withSession("updating", (id) => ragApi.removeExtra(id, index)),
    suggest: () => {
      if (!session) return;
      run("suggesting", async () => {
        const found = await ragApi.suggest(session.id);
        setSuggestions(found.items);
      });
    },
    finish: (onDone) => {
      if (!session) return;
      run("saving", async () => {
        setOutcome(await ragApi.finish(session.id));
        setSession(await ragApi.session(session.id));
        setPreview(true);
        onDone?.(session.id);
      });
    },
    retry: () => {
      if (last.current) run(last.current.op, last.current.action);
    },
    restart: () => {
      setSearch(null);
      setSession(null);
      setOutcome(null);
      setVerdict(null);
      setSuggestions(null);
      setPreview(false);
      setManual(null);
      setFailure(null);
      setAutomatic(true);
      setDraft("");
    },
  };
}
