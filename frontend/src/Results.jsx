import { useState } from "react";
import { ShieldCheck, ShieldAlert, ChevronDown } from "lucide-react";
import { Badge } from "./components/ui/badge";
import { cn } from "./lib/utils";
import { useI18n } from "./lib/i18n.jsx";
import { DetectionCardFor } from "./components/detections";

function PassedSection({ passed }) {
  const { t } = useI18n();
  const [show, setShow] = useState(false);
  if (passed.length === 0) return null;
  return (
    <div>
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="flex w-full items-center justify-between rounded-lg border border-border bg-background/40 px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <span className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-success" />
          {t("results.passed").replace("{count}", passed.length)}
        </span>
        <ChevronDown
          className={cn("h-4 w-4 transition-transform", show && "rotate-180")}
        />
      </button>
      {show && (
        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
          {passed.map((d, i) => (
            <DetectionCardFor
              key={d.service_id ?? `${d.type}-${i}`}
              detection={d}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PageDetections({ detections }) {
  const flagged = detections.filter((d) => d.flagged);
  const passed = detections.filter((d) => !d.flagged);
  return (
    <div className="flex flex-col gap-3">
      {flagged.length > 0 && (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {flagged.map((d, i) => (
            <DetectionCardFor
              key={d.service_id ?? `${d.type}-${i}`}
              detection={d}
            />
          ))}
        </div>
      )}
      <PassedSection passed={passed} />
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
    return <p className="text-sm text-muted-foreground">{t("results.empty")}</p>;
  }

  const pages = result.pages || [];
  const allDetections = pages.flatMap((p) => p.detections || []);
  const flagged = allDetections.filter((d) => d.flagged);
  const anyFlagged = flagged.length > 0;
  const multiPage = pages.length > 1;

  const sevCount = (level) => flagged.filter((d) => d.severity === level).length;
  const highCount = sevCount("high");
  const mediumCount = sevCount("medium");
  const lowCount = sevCount("low");

  return (
    <div className="flex flex-col gap-4">
      {/* Summary banner */}
      <div
        className={cn(
          "rounded-lg border p-4",
          anyFlagged
            ? "border-destructive/50 bg-destructive/10"
            : "border-success/50 bg-success/10"
        )}
      >
        <div className="flex items-center gap-3">
          {anyFlagged ? (
            <ShieldAlert className="h-6 w-6 shrink-0 text-destructive" />
          ) : (
            <ShieldCheck className="h-6 w-6 shrink-0 text-success" />
          )}
          <div className="min-w-0 flex-1">
            <p
              className={cn(
                "font-semibold",
                anyFlagged ? "text-destructive" : "text-success"
              )}
            >
              {anyFlagged
                ? t("results.verdict.danger")
                : t("results.verdict.safe")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("results.summary")
                .replace("{flagged}", flagged.length)
                .replace("{total}", allDetections.length)}
            </p>
          </div>
          {result.metadata?.mock && <Badge variant="muted">mock</Badge>}
        </div>

        {anyFlagged && (
          <div className="mt-3 flex flex-wrap gap-2">
            {highCount > 0 && (
              <Badge variant="destructive">
                {highCount} {t("severity.high")}
              </Badge>
            )}
            {mediumCount > 0 && (
              <Badge variant="default">
                {mediumCount} {t("severity.medium")}
              </Badge>
            )}
            {lowCount > 0 && (
              <Badge variant="muted">
                {lowCount} {t("severity.low")}
              </Badge>
            )}
          </div>
        )}
      </div>

      {/* Per-page detections */}
      {pages.map((page, idx) => (
        <div key={page.page_number ?? idx} className="flex flex-col gap-3">
          {multiPage && (
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <span className="rounded-md bg-muted px-2 py-0.5 text-xs">
                {t("results.page").replace(
                  "{n}",
                  page.page_number ?? idx + 1
                )}
              </span>
            </div>
          )}
          <PageDetections detections={page.detections || []} />
        </div>
      ))}
    </div>
  );
}
