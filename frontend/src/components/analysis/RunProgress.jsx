import { Loader2, CheckCircle2, XCircle, Circle, Ban } from "lucide-react";
import { Badge } from "../ui/badge";
import { cn } from "../../lib/utils";
import { useI18n } from "../../lib/i18n.jsx";

const RUN_STATUS = {
  pending: { Icon: Circle, className: "text-muted-foreground" },
  running: { Icon: Loader2, className: "text-primary animate-spin" },
  success: { Icon: CheckCircle2, className: "text-success" },
  error: { Icon: XCircle, className: "text-destructive" },
  revoked: { Icon: Ban, className: "text-muted-foreground" },
};

function ServiceRunRow({ run, t }) {
  const status = run.task?.status || "pending";
  const progress = run.task?.progress ?? 0;
  const meta = RUN_STATUS[status] || RUN_STATUS.pending;
  const { Icon } = meta;
  return (
    <div className="rounded-lg border border-border bg-background/40 p-3">
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4 shrink-0", meta.className)} />
        <span className="flex-1 truncate text-sm font-medium">
          {run.service.name}
        </span>
        <Badge variant={status === "error" ? "destructive" : "muted"}>
          {t(`status.${status}`)}
        </Badge>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            status === "error" ? "bg-destructive" : "bg-primary"
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
      {run.task?.error && (
        <p className="mt-1.5 text-xs text-destructive">{run.task.error}</p>
      )}
    </div>
  );
}

/**
 * Group-run progress panel shown above the results when tasks are running.
 */
export default function RunProgress({ group, runs, doneCount }) {
  const { t } = useI18n();
  if (!runs.length) return null;
  return (
    <div className="mb-4 rounded-lg border border-border bg-background/40 p-3">
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="font-medium">{t("analyze.group.title")}</span>
        <span className="text-muted-foreground">
          {t("analyze.group.progress")
            .replace("{done}", doneCount)
            .replace("{total}", runs.length)}
        </span>
      </div>
      {group && (
        <div className="mb-2 text-xs text-muted-foreground">
          {t("task.id")} : <code className="text-foreground">{group.id}</code>
        </div>
      )}
      <div className="flex flex-col gap-2">
        {runs.map((run) => (
          <ServiceRunRow key={run.task.id} run={run} t={t} />
        ))}
      </div>
    </div>
  );
}
