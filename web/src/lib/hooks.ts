"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { errorMessage } from "./api";

interface ResourceState<T> {
  key: string | null;
  data?: T;
  error?: string;
  status?: number;
}

function statusOf(e: unknown): number | undefined {
  const s = (e as { status?: unknown } | null)?.status;
  return typeof s === "number" ? s : undefined;
}

/**
 * Loads a resource identified by `key`. The loader is re-run whenever the key changes or `reload` is called.
 * State is only set from promise callbacks, never synchronously inside the effect.
 */
export function useResource<T>(key: string | null, load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<ResourceState<T>>({ key: null });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (key === null) return;
    const ctrl = new AbortController();
    load(ctrl.signal).then(
      (data) => {
        if (!ctrl.signal.aborted) setState({ key, data });
      },
      (e: unknown) => {
        if (!ctrl.signal.aborted) setState({ key, error: errorMessage(e), status: statusOf(e) });
      },
    );
    return () => ctrl.abort();
    // The loader is identified by `key`; `nonce` forces a refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, nonce]);

  const current = key !== null && state.key === key ? state : undefined;
  const reload = useCallback(() => {
    setState({ key: null });
    setNonce((n) => n + 1);
  }, []);

  return {
    data: current?.data,
    error: current?.error ?? null,
    errorStatus: current?.status,
    loading: key !== null && current === undefined,
    reload,
  };
}

const listeners = new Set<() => void>();

function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

/** A localStorage-backed string, read through useSyncExternalStore so the server render and hydration agree (null). */
export function useStoredValue(storageKey: string): [string | null, (v: string | null) => void] {
  const value = useSyncExternalStore(
    subscribe,
    () => {
      try {
        return window.localStorage.getItem(storageKey);
      } catch {
        return null;
      }
    },
    () => null,
  );
  const set = useCallback(
    (v: string | null) => {
      try {
        if (v === null) window.localStorage.removeItem(storageKey);
        else window.localStorage.setItem(storageKey, v);
      } catch {
        /* private mode or blocked storage: the value simply does not persist */
      }
      listeners.forEach((l) => l());
    },
    [storageKey],
  );
  return [value, set];
}

/** Returns `value` after it has been stable for `ms` milliseconds. */
export function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

/** True once the component has mounted on the client (false during SSR and hydration). */
export function useMounted(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}
