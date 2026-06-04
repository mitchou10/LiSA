import { Badge } from "../ui/badge";
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
 * Generic card rendering the fields shared by every DetectionResult.
 * Type-specific cards wrap this and pass a title, icon and optional children.
 */
export default function DetectionCard({ titleKey, icon: Icon, detection, children }) {
  const { t } = useI18n();
  const { flagged, confidence, severity, action } = detection;
  const pct = Math.round((confidence ?? 0) * 100);

  return (
    <div className="rounded-lg border border-border bg-background/40 p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-sm font-medium">
          {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
          {t(titleKey)}
        </span>
        <Badge variant={flagged ? "destructive" : "success"}>
          {flagged ? t("results.detected") : t("results.ok")}
        </Badge>
      </div>

      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            flagged ? "bg-destructive" : "bg-success"
          )}
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span>
          {t("results.score")} : {Number(confidence ?? 0).toFixed(3)} ({pct}%)
        </span>
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

      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}
