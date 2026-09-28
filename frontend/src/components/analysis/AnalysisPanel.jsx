import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../ui/card";
import Results from "../../Results";
import RunProgress from "./RunProgress";
import { useI18n } from "../../lib/i18n.jsx";

/**
 * Shared two-column layout for an analysis tab: input on the left,
 * results + run progress on the right. Each tab owns its own `analysis`
 * instance (from useAnalysis), so results are fully independent between tabs.
 *
 * Props:
 *  - analysis: the useAnalysis() return value
 *  - inputTitle / inputDesc: i18n keys for the input card header
 *  - children: the input form (textarea, dropzone, …)
 *  - ResultComponent: optional custom results component (defaults to Results).
 *      Receives `{ result, loading, error, analysis }`.
 */
export default function AnalysisPanel({
  analysis,
  inputTitleKey,
  inputDescKey,
  children,
  ResultComponent = Results,
  resultProps = {},
}) {
  const { t } = useI18n();

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Left: input + service selection */}
      <Card>
        <CardHeader>
          <CardTitle>{t(inputTitleKey)}</CardTitle>
          <CardDescription>{t(inputDescKey)}</CardDescription>
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>

      {/* Right: group progress + consolidated results */}
      <Card>
        <CardHeader>
          <CardTitle>{t("analyze.results.title")}</CardTitle>
          <CardDescription>{t("analyze.results.desc")}</CardDescription>
        </CardHeader>
        <CardContent>
          <RunProgress
            group={analysis.group}
            runs={analysis.runs}
            doneCount={analysis.doneCount}
          />
          <ResultComponent
            result={analysis.result}
            loading={analysis.showLoading}
            error={analysis.error}
            analysis={analysis}
            {...resultProps}
          />
        </CardContent>
      </Card>
    </div>
  );
}
