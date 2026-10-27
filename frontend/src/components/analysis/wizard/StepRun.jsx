import { AlertTriangle, CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { formatDuration } from "../../../lib/runModel";
import { cn } from "../../../lib/utils";
import { useI18n } from "../../../lib/i18n.jsx";

const ICON = {
  pending: { Icon: Circle, className: "text-muted-foreground" },
  running: { Icon: Loader2, className: "text-primary animate-spin" },
  success: { Icon: CheckCircle2, className: "text-success" },
  error: { Icon: XCircle, className: "text-destructive" },
  revoked: { Icon: XCircle, className: "text-muted-foreground" },
};

/** Step 3: every task of the run with its progress, until the run ends. */
export default function StepRun({ run, uploading, error }) {
  const { t } = useI18n();
  const steps = run?.steps ?? [];
  const done = steps.filter((s) => s.status === "success").length;
  const total = steps.length;
  const overall = total ? Math.round((done / total) * 100) : 0;

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">
            {uploading ? t("run.uploading") : t("wiz.run.overall").replace("{done}", done).replace("{total}", total)}
          </span>
          <span className="tabular-nums text-muted-foreground">{overall}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${overall}%` }} />
        </div>
      </div>

      <ul className="space-y-2">
        {steps.map((step) => {
          const meta = ICON[step.status] ?? ICON.pending;
          const { Icon } = meta;
          return (
            <li key={step.task_id} className="rounded-lg border border-border bg-background/40 p-3">
              <div className="flex items-center gap-2">
                <Icon className={cn("h-4 w-4 shrink-0", meta.className)} />
                <span className="flex-1 text-sm font-medium">{t(`run.step.${step.step}`)}</span>
                {step.duration != null && (
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {formatDuration(step.duration)}
                  </span>
                )}
                <span className="text-xs text-muted-foreground">{t(`status.${step.status}`)}</span>
              </div>
              {step.status === "running" && (
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${step.progress ?? 0}%` }}
                  />
                </div>
              )}
              {step.error && <p className="mt-1.5 text-xs text-destructive">{step.error}</p>}
            </li>
          );
        })}
      </ul>

      {error && (
        <p className="flex items-center gap-2 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4" />
          {error}
        </p>
      )}
    </div>
  );
}
