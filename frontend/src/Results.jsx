import { ShieldCheck, ShieldAlert, Clock } from "lucide-react";
import { Badge } from "./components/ui/badge";
import { cn } from "./lib/utils";
import { useI18n } from "./lib/i18n.jsx";

function ScannerRow({ name, flagged, score }) {
  const { t } = useI18n();
  const pct = Math.round((score ?? 0) * 100);
  return (
    <div className="rounded-lg border border-border bg-background/40 p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{t(`scanner.${name}`)}</span>
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
      <div className="mt-1.5 text-xs text-muted-foreground">
        {t("results.score")} : {Number(score ?? 0).toFixed(3)} ({pct}%)
      </div>
    </div>
  );
}

export default function Results({ result, loading, error }) {
  const { t } = useI18n();
  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        <div className="h-16 animate-pulse rounded-lg bg-muted" />
        <div className="h-20 animate-pulse rounded-lg bg-muted" />
        <div className="h-20 animate-pulse rounded-lg bg-muted" />
      </div>
    );
  }

  if (!result) {
    return (
      <p className="text-sm text-muted-foreground">
        {t("results.empty")}
      </p>
    );
  }

  const predictions = result.predictions || {};
  const scores = result.scores || {};
  const names = Array.from(
    new Set([...Object.keys(predictions), ...Object.keys(scores)])
  );
  const anyFlagged = names.some((n) => predictions[n]);

  return (
    <div className="flex flex-col gap-4">
      <div
        className={cn(
          "flex items-center gap-3 rounded-lg border p-4 font-medium",
          anyFlagged
            ? "border-destructive/50 bg-destructive/10 text-destructive"
            : "border-success/50 bg-success/10 text-success"
        )}
      >
        {anyFlagged ? (
          <ShieldAlert className="h-5 w-5 shrink-0" />
        ) : (
          <ShieldCheck className="h-5 w-5 shrink-0" />
        )}
        <span>
          {anyFlagged
            ? t("results.verdict.danger")
            : t("results.verdict.safe")}
        </span>
      </div>

      <div className="flex flex-col gap-3">
        {names.map((name) => (
          <ScannerRow
            key={name}
            name={name}
            flagged={predictions[name]}
            score={scores[name]}
          />
        ))}
      </div>

      {result.process_time !== undefined && (
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Clock className="h-3.5 w-3.5" />
          {t("results.processTime")} : {Number(result.process_time).toFixed(3)} s
          {result.metadata?.mock && (
            <Badge variant="muted" className="ml-2">
              mock
            </Badge>
          )}
        </div>
      )}
    </div>
  );
}
