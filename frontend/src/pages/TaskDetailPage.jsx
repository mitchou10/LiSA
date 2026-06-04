import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Braces, AlertTriangle } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import Results from "../Results";
import { TASKS } from "../lib/mockData";
import { mockAnalyze } from "../lib/mockApi";
import { useI18n } from "../lib/i18n.jsx";

export default function TaskDetailPage() {
  const { t } = useI18n();
  const { taskId } = useParams();
  const task = useMemo(() => TASKS.find((x) => x.id === taskId), [taskId]);

  const content = useMemo(() => {
    const pages = task?.input?.pages || [];
    return pages.map((p) => p.content).join("\n\n");
  }, [task]);

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!task || task.status !== "success") return;
    let cancelled = false;
    setLoading(true);
    mockAnalyze(content)
      .then((res) => {
        if (!cancelled) setResult(res);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [task, content]);

  const backLink = (
    <Link
      to="/services"
      className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
    >
      <ArrowLeft className="h-4 w-4" />
      {t("taskDetail.back")}
    </Link>
  );

  if (!task) {
    return (
      <div className="flex flex-col gap-4">
        {backLink}
        <Card>
          <CardContent className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
            <AlertTriangle className="h-4 w-4" />
            {t("taskDetail.notFound").replace("{id}", taskId)}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (task.status !== "success") {
    return (
      <div className="flex flex-col gap-4">
        {backLink}
        <Card>
          <CardContent className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
            <AlertTriangle className="h-4 w-4" />
            {t("taskDetail.notFinished")}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        {backLink}
        <span className="font-mono text-sm font-medium">{task.id}</span>
        <code className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
          {task.route}
        </code>
        <Badge variant="muted">{task.service}</Badge>
        <Badge variant="success">{t("status.success")}</Badge>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Input payload (InputData) */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Braces className="h-4 w-4" />
              {t("taskDetail.input")}
            </CardTitle>
            <CardDescription>{t("taskDetail.inputDesc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="max-h-[60vh] overflow-auto rounded-lg border border-border bg-background/60 p-3 text-xs text-foreground">
              {JSON.stringify(task.input ?? {}, null, 2)}
            </pre>
          </CardContent>
        </Card>

        {/* Analysis results */}
        <Card>
          <CardHeader>
            <CardTitle>{t("analyze.results.title")}</CardTitle>
            <CardDescription>{t("analyze.results.desc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Results result={result} loading={loading} error={null} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
