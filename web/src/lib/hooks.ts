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

/* A small in-memory cache shared by every `useResource` on the page. A key seen in the last `FRESH_MS` is served
 * without a request; an older one is shown at once and refreshed in the background; two components asking for the
 * same key at the same time share one request. The cache lives for the page session only. */
interface Entry {
  data: unknown;
  at: number;
}
const memory = new Map<string, Entry>();
const inflight = new Map<string, Promise<unknown>>();
const FRESH_MS = 30_000;

function fetchShared<T>(key: string, load: (signal: AbortSignal) => Promise<T>): Promise<T> {
  const running = inflight.get(key) as Promise<T> | undefined;
  if (running) return running;
  const p = load(new AbortController().signal)
    .then((data) => {
      memory.set(key, { data, at: Date.now() });
      return data;
    })
    .finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}

/** Stores a response under `key` so a later `useResource(key)` renders it without another request. */
export function primeResource(key: string, data: unknown): void {
  memory.set(key, { data, at: Date.now() });
}

/**
 * Loads a resource identified by `key`. The loader is re-run whenever the key changes or `reload` is called, and
 * skipped while a fresh copy sits in the page cache. State is only set from promise callbacks, never synchronously
 * inside the effect; a cached value is read during render instead.
 */
export function useResource<T>(key: string | null, load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<ResourceState<T>>({ key: null });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (key === null) return;
    const hit = memory.get(key);
    if (hit && nonce === 0 && Date.now() - hit.at < FRESH_MS) return;
    let cancelled = false;
    fetchShared(key, load).then(
      (data) => {
        if (!cancelled) setState({ key, data });
      },
      (e: unknown) => {
        if (!cancelled) setState({ key, error: errorMessage(e), status: statusOf(e) });
      },
    );
    return () => {
      cancelled = true;
    };
    // The loader is identified by `key`; `nonce` forces a refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, nonce]);

  const cached = key !== null ? memory.get(key) : undefined;
  const current: ResourceState<T> | undefined =
    key !== null && state.key === key ? state : cached ? { key, data: cached.data as T } : undefined;
  const reload = useCallback(() => {
    if (key !== null) memory.delete(key);
    setState({ key: null });
    setNonce((n) => n + 1);
  }, [key]);

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
