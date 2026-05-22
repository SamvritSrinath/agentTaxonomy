import { useEffect, useState } from "react";

/**
 * State returned by `useAsyncResource` for API-backed UI regions.
 */
export interface AsyncResourceState<T> {
  /** Loaded data, or null before the first successful request. */
  data: T | null;
  /** Whether the request is currently in flight. */
  loading: boolean;
  /** Error message from the latest failed request. */
  error: string | null;
  /** Re-run the resource loader. */
  reload: () => void;
}

/**
 * Load an asynchronous resource and expose loading/error state.
 *
 * @param loader - Function that returns a promise for the resource data.
 * @param dependencies - React dependency list controlling reload behavior.
 * @returns Resource state for rendering.
 */
export function useAsyncResource<T>(loader: () => Promise<T>, dependencies: unknown[]): AsyncResourceState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    loader()
      .then((value) => {
        if (active) {
          setData(value);
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(caught instanceof Error ? caught.message : String(caught));
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [...dependencies, nonce]);

  return {
    data,
    loading,
    error,
    reload: () => setNonce((value) => value + 1)
  };
}
