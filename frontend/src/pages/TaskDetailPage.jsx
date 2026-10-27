import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Braces, AlertTriangle, Loader2 } from "lucide-react";
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
import { getTask, getTaskChildren, getServices } from "../lib/api";
import { useI18n } from "../lib/i18n.jsx";

const TERMINAL = new Set(["success", "error", "revoked"]);

// Merge a task's own output and its children's outputs into a single pages[].
function consolidate(tasks, svcById) {
  const byPage = new Map();
  for (const task of tasks) {
    const pages = task?.output_data?.pages || [];
    const svcName = task.service_id
      ? svcById.get(task.service_id)?.name ?? "service"
      : "service";
    for (const page of pages) {
      const key = page.page_number ?? 1;
      if (!byPage.has(key))
        byPage.set(key, { page_number: key, detections: [] });
      const dets = (page.detections || []).map((d) => ({
        ...d,
        service: svcName,
      }));
      byPage.get(key).detections.push(...dets);
    }
  }
  const pages = [...byPage.values()].sort(
    (a, b) => (a.page_number ?? 0) - (b.page_number ?? 0)
  );
  return pages.length ? { pages } : null;
}

export default function TaskDetailPage() {
  const { t } = useI18n();
  const { taskId } = useParams();

  const mockTask = useMemo(() => TASKS.find((x) => x.id === taskId), [taskId]);

  const [task, setTask] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  // Fetch the real task (+ children + services) from the backend.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    setResult(null);

    Promise.all([
      getTask(taskId),
      getTaskChildren(taskId).catch(() => []),
      getServices().catch(() => []),
    ])
      .then(([real, children, services]) => {
        if (cancelled) return;
        const svcById = new Map(
          (Array.isArray(services) ? services : []).map((s) => [s.id, s])
        );
        setTask(real);
        const all = [real, ...(Array.isArray(children) ? children : [])];
        setResult(consolidate(all, svcById));
      })
      .catch(() => {
        if (cancelled) return;
        // Fall back to mock data (when the API is down or task is a mock id).
        if (mockTask) {
          setTask({ ...mockTask, _mock: true });
          const content = (mockTask.input?.pages || [])
            .map((p) => p.content)
            .join("\n\n");
          if (mockTask.status === "success") {
            mockAnalyze(content).then((res) => {
              if (!cancelled) setResult(res);
            });
          }
        } else {
          setNotFound(true);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [taskId, mockTask]);

  const status = task?.status;
  const serviceLabel = task?._mock
    ? task.service
    : task?.service_id
      ? task.service_id.slice(0, 8)
      : "group";
  const routeLabel = task?._mock ? task.route : task?.service_id ? "" : "/group";
  const inputPayload = task?._mock ? task.input : task?.input_data;

  const backLink = (
    <Link
      to="/services"
      className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
    >
      <ArrowLeft className="h-4 w-4" />
      {t("taskDetail.back")}
    </Link>
  );

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        {backLink}
        <Card>
          <CardContent className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t("analyze.group.waiting")}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (notFound || !task) {
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

  if (!TERMINAL.has(status)) {
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

  const statusVariant =
    status === "error"
      ? "destructive"
      : status === "success"
        ? "success"
        : "muted";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        {backLink}
        <span className="font-mono text-sm font-medium">{task.id}</span>
        {routeLabel && (
          <code className="rounded-[0.25rem] bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
            {routeLabel}
          </code>
        )}
        <Badge variant="muted">{serviceLabel}</Badge>
        <Badge variant={statusVariant}>{t(`status.${status}`)}</Badge>
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
              {JSON.stringify(inputPayload ?? {}, null, 2)}
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
            <Results result={result} loading={false} error={null} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
