import { ShieldCheck, ShieldAlert } from "lucide-react";
import { Badge } from "./components/ui/badge";
import { cn } from "./lib/utils";
import { useI18n } from "./lib/i18n.jsx";
import { DetectionCardFor } from "./components/detections";

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
    return <p className="text-sm text-muted-foreground">{t("results.empty")}</p>;
  }

  const detections = result.detections || [];
  const anyFlagged = detections.some((d) => d.flagged);

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
          {anyFlagged ? t("results.verdict.danger") : t("results.verdict.safe")}
        </span>
        {result.metadata?.mock && (
          <Badge variant="muted" className="ml-auto">
            mock
          </Badge>
        )}
      </div>

      <div className="flex flex-col gap-3">
        {detections.map((d, i) => (
          <DetectionCardFor key={d.service_id ?? `${d.type}-${i}`} detection={d} />
        ))}
      </div>
    </div>
  );
}
