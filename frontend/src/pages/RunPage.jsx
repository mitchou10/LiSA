import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Loader2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import Stepper from "../components/analysis/wizard/Stepper";
import StepRun from "../components/analysis/wizard/StepRun";
import StepResults from "../components/analysis/wizard/StepResults";
import TaskDetailPage from "./TaskDetailPage";
import { useRunView } from "../hooks/useRunView";
import { useI18n } from "../lib/i18n.jsx";

const RUN = 2;
const RESULTS = 3;
const TERMINAL = ["success", "error", "revoked"];

/**
 * An earlier run, opened from "My tasks": the progress while it is running,
 * the results once it is over, with the same views as the analysis page.
 */
export default function RunPage() {
  const { t } = useI18n();
  const { taskId } = useParams();
  const view = useRunView(taskId);
  const [step, setStep] = useState(null); // null: follow the run

  useEffect(() => setStep(null), [taskId]);

  const back = (
    <Link
      to="/my-tasks"
      className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
    >
      <ArrowLeft className="h-4 w-4" />
      {t("taskDetail.back")}
    </Link>
  );

  if (view.loading)
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        {back}
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  if (view.error)
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        {back}
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <AlertTriangle className="h-4 w-4" />
          {t("taskDetail.notFound").replace("{id}", taskId)}
        </p>
      </div>
    );
  // A step of a run: show the run it belongs to.
  if (view.parent.parent_task_id) return <Navigate to={`/analysis/${view.parent.parent_task_id}`} replace />;
  // Not a run (a task sent to a service directly): the plain detail page.
  if (!view.isRun) return <TaskDetailPage />;

  const { run, source, parent } = view;
  const finished = TERMINAL.includes(run.status);
  const current = step ?? (finished ? RESULTS : RUN);
  const labels = ["wiz.step.source", "wiz.step.analysis", "wiz.step.run", "wiz.step.results"].map(t);
  const title =
    current === RESULTS
      ? ["wiz.results.title", "wiz.results.desc"]
      : ["wiz.run.title", "wiz.run.desc"];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        {back}
        <span className="font-mono text-sm">{taskId.slice(0, 8)}</span>
        <Badge variant="muted">{t(`wiz.source.kind.${parent.input_data?.source ?? "text"}`)}</Badge>
        <Badge variant={run.status === "error" ? "destructive" : run.status === "success" ? "success" : "muted"}>
          {t(`status.${run.status}`)}
        </Badge>
        <span className="ml-auto text-xs text-muted-foreground">
          {new Date(parent.created_at).toLocaleString()}
        </span>
      </div>

      {/* Source and Analysis were chosen when the run was started: not editable here. */}
      <Stepper
        steps={labels}
        current={current}
        reached={finished ? RESULTS : RUN}
        from={RUN}
        canGo
        onGo={setStep}
      />

      <Card>
        <CardHeader>
          <CardTitle>{t(title[0])}</CardTitle>
          <CardDescription>{t(title[1])}</CardDescription>
        </CardHeader>
        <CardContent>
          {current === RESULTS ? (
            <StepResults run={run} source={source} />
          ) : (
            <StepRun run={run} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
