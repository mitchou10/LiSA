import { useEffect, useState } from "react";
import { cn } from "../lib/utils";
import { getHealth } from "../lib/api";
import { useI18n } from "../lib/i18n.jsx";

const POLL_MS = 15000;

export default function HealthIndicator() {
  const { t } = useI18n();
  // "loading" | "ok" | "down"
  const [state, setState] = useState("loading");

  useEffect(() => {
    let active = true;

    const check = async () => {
      try {
        const data = await getHealth();
        if (!active) return;
        setState(data?.database === "ok" ? "ok" : "down");
      } catch {
        if (active) setState("down");
      }
    };

    check();
    const id = setInterval(check, POLL_MS);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const label =
    state === "ok"
      ? t("health.online")
      : state === "down"
        ? t("health.offline")
        : t("health.checking");

  const dotColor =
    state === "ok"
      ? "bg-success"
      : state === "down"
        ? "bg-destructive"
        : "bg-muted-foreground";

  return (
    <div
      className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground"
      title={`API: ${label}`}
    >
      <span className="relative flex h-2.5 w-2.5">
        {state === "ok" && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
        )}
        <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", dotColor)} />
      </span>
      {label}
    </div>
  );
}
