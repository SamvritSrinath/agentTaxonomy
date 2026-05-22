import { useEffect, useState } from "react";
import { getOpenRouterUsage } from "../api/client";
import type { OpenRouterUsage } from "../api/types";

const POLL_MS = 60_000;

export function OpenRouterSpendWidget() {
  const [usage, setUsage] = useState<OpenRouterUsage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getOpenRouterUsage();
        if (!cancelled) {
          setUsage(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      }
    }
    void load();
    const timer = window.setInterval(() => void load(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const keyData = usage?.key?.data;
  const daily = asNumber(keyData?.usage_daily);
  const monthly = asNumber(keyData?.usage_monthly);

  return (
    <div className="spend-widget" title={error ?? undefined}>
      <span className="spend-label">OpenRouter</span>
      {error ? (
        <span className="spend-error">unavailable</span>
      ) : (
        <>
          <span>day {formatUsd(daily)}</span>
          <span>mo {formatUsd(monthly)}</span>
        </>
      )}
    </div>
  );
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function formatUsd(value: number | null | undefined): string {
  if (value == null) {
    return "—";
  }
  return `$${value.toFixed(2)}`;
}
