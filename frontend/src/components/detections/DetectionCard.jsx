import { useState } from "react";
import { Info } from "lucide-react";
import { Badge } from "../ui/badge";
import { Dialog } from "../ui/dialog";
import { cn } from "../../lib/utils";
import { useI18n } from "../../lib/i18n.jsx";

const SEVERITY_VARIANT = {
  low: "muted",
  medium: "default",
  high: "destructive",
};

const ACTION_VARIANT = {
  allow: "success",
  redact: "default",
  block: "destructive",
};

/**
 * Compact card for a single DetectionResult.
 * Header (title, score, badges) is always visible; clicking opens a modal
 * with the full details + type-specific content (children).
 */
export default function DetectionCard({ titleKey, icon: Icon, detection, children }) {
  const { t } = useI18n();
  const { flagged, confidence, severity, action, details } = detection;
  const pct = Math.round((confidence ?? 0) * 100);
  const detailEntries =
    details && typeof details === "object" ? Object.entries(details) : [];
  const hasBody = Boolean(children) || detailEntries.length > 0;

  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        disabled={!hasBody}
        onClick={() => setOpen(true)}
        className={cn(
          "flex w-full items-center gap-3 rounded-lg border bg-background/40 p-3 text-left transition-colors",
          flagged ? "border-destructive/40" : "border-border",
          hasBody && "cursor-pointer hover:bg-background/70"
        )}
      >
        <span
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-md",
            flagged
              ? "bg-destructive/15 text-destructive"
              : "bg-success/15 text-success"
          )}
        >
          {Icon && <Icon className="h-4 w-4" />}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-sm font-medium">{t(titleKey)}</span>
            <span
              className={cn(
                "shrink-0 text-xs font-semibold tabular-nums",
                flagged ? "text-destructive" : "text-muted-foreground"
              )}
            >
              {pct}%
            </span>
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  flagged ? "bg-destructive" : "bg-success"
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
            {severity && flagged && (
              <Badge variant={SEVERITY_VARIANT[severity] ?? "muted"}>
                {t(`severity.${severity}`)}
              </Badge>
            )}
            {action && flagged && (
              <Badge variant={ACTION_VARIANT[action] ?? "muted"}>
                {t(`action.${action}`)}
              </Badge>
            )}
          </div>
        </div>

        {hasBody && (
          <Info className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </button>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={t(titleKey)}
        icon={Icon}
      >
        <div className="flex flex-col gap-4">
          {/* Verdict + metrics */}
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={flagged ? "destructive" : "success"}>
              {flagged ? t("results.detected") : t("results.ok")}
            </Badge>
            {severity && (
              <Badge variant={SEVERITY_VARIANT[severity] ?? "muted"}>
                {t(`severity.${severity}`)}
              </Badge>
            )}
            {action && (
              <Badge variant={ACTION_VARIANT[action] ?? "muted"}>
                {t(`action.${action}`)}
              </Badge>
            )}
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
              <span>{t("results.score")}</span>
              <span className="font-semibold tabular-nums text-foreground">
                {Number(confidence ?? 0).toFixed(3)} ({pct}%)
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  "h-full rounded-full",
                  flagged ? "bg-destructive" : "bg-success"
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          {children}

          {detailEntries.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t("results.details")}
              </p>
              <dl className="grid grid-cols-1 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-2">
                {detailEntries.map(([key, value]) => (
                  <div
                    key={key}
                    className="flex items-baseline justify-between gap-2 border-b border-border/60 pb-1"
                  >
                    <dt className="text-muted-foreground">{key}</dt>
                    <dd className="text-right font-medium text-foreground">
                      {typeof value === "object"
                        ? JSON.stringify(value)
                        : String(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {detection.service_id && (
            <p className="text-xs text-muted-foreground">
              {t("results.service")} : {detection.service_id}
            </p>
          )}
        </div>
      </Dialog>
    </>
  );
}
