import { useMemo } from "react";
import { ChevronDown } from "lucide-react";
import { buildPages, formatDuration } from "../../../lib/runModel";
import { useI18n } from "../../../lib/i18n.jsx";
import RunResults from "../RunResults";
import ResultsViewer from "./ResultsViewer";

/**
 * Step 4: one line of summary, the document next to what was found (with the
 * blur and export right below), and the raw result of each task folded away.
 */
export default function StepResults({ run, source }) {
  const { t } = useI18n();
  const pages = useMemo(() => buildPages(run, source), [run, source]);

  const entities = pages.reduce((n, p) => n + p.entities.length, 0);
  const alerts = pages.filter((p) => p.unsafe).length;
  const failed = run.steps.filter((s) => s.status === "error").length;

  const parts = [
    `${pages.length} ${t("wiz.results.pages").toLowerCase()}`,
    `${entities} ${t("wiz.results.entities").toLowerCase()}`,
    alerts ? t("wiz.results.alerts").replace("{n}", alerts) : t("wiz.results.clear"),
    run.duration != null ? formatDuration(run.duration) : null,
  ].filter(Boolean);

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        {parts.join(" · ")}
        {failed > 0 && (
          <span className="text-destructive"> · {t("wiz.results.failedN").replace("{n}", failed)}</span>
        )}
      </p>

      <ResultsViewer run={run} source={source} />

      <details className="group rounded-xl border border-border">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium">
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
          {t("wiz.results.details")}
          <span className="font-normal text-muted-foreground">{t("wiz.results.details.hint")}</span>
        </summary>
        <div className="border-t border-border p-4">
          <RunResults run={run} />
        </div>
      </details>
    </div>
  );
}
