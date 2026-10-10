import { useEffect, useRef, useState } from "react";

export type Resource<T> = {
  readonly data: T | undefined;
  readonly error: Error | null;
  readonly loading: boolean;
};

const inflight = new Map<string, Promise<unknown>>();

function shared<T>(key: string, load: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key);
  if (existing) return existing as Promise<T>;
  const promise = load().finally(() => inflight.delete(key));
  inflight.set(key, promise);
  return promise;
}

export function useResource<T>(load: () => Promise<T>, key: string): Resource<T> {
  const loader = useRef(load);
  loader.current = load;
  const [state, setState] = useState<Resource<T>>({ data: undefined, error: null, loading: true });

  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    shared(key, () => loader.current()).then(
      (data) => live && setState({ data, error: null, loading: false }),
      (error: Error) => live && setState((s) => ({ ...s, error, loading: false })),
    );
    return () => {
      live = false;
    };
  }, [key]);

  return state;
}
