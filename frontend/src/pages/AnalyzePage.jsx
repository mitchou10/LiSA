import { useEffect, useMemo, useRef, useState } from "react";
import {
  FileText,
  Braces,
  Play,
  Loader2,
  CheckCircle2,
  XCircle,
  Circle,
  Ban,
} from "lucide-react";
import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../components/ui/card";
import { Textarea } from "../components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Badge } from "../components/ui/badge";
import { cn } from "../lib/utils";
import Results from "../Results";
import { mockAnalyze } from "../lib/mockApi";
import { submitTask, getTask, getServices } from "../lib/api";
import { SERVICES as MOCK_SERVICES } from "../lib/mockData";
import { useI18n } from "../lib/i18n.jsx";

const USER_ID = "web-user";
const TERMINAL = new Set(["success", "error", "revoked"]);
const POLL_INTERVAL = 1200;
const MAX_POLLS = 100;

// Build a backend `InputData` payload (metadata + pages[]) from the editor.
function buildInputData(tab, text, json) {
  if (tab === "json") {
    const parsed = JSON.parse(json); // throws if invalid
    if (parsed && Array.isArray(parsed.pages)) {
      return {
        metadata: parsed.metadata ?? { source: "web" },
        pages: parsed.pages,
      };
    }
    const content =
      typeof parsed === "string" ? parsed : JSON.stringify(parsed, null, 2);
    return {
      metadata: { source: "web", kind: "json" },
      pages: [{ content, page_number: 1 }],
    };
  }
  return {
    metadata: { source: "web", kind: "text" },
    pages: [{ content: text, page_number: 1 }],
  };
}

// Merge every finished child's `Analyse` output into a single pages[] tree.
function consolidate(runs) {
  const byPage = new Map();
  for (const run of runs) {
    const pages = run.task?.output_data?.pages || [];
    for (const page of pages) {
      const key = page.page_number ?? 1;
      if (!byPage.has(key))
        byPage.set(key, { page_number: key, detections: [] });
      const dets = (page.detections || []).map((d) => ({
        ...d,
        service: run.service.name,
      }));
      byPage.get(key).detections.push(...dets);
    }
  }
  const pages = [...byPage.values()].sort(
    (a, b) => (a.page_number ?? 0) - (b.page_number ?? 0)
  );
  return pages.length ? { pages } : null;
}

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

export default function AnalyzePage() {
  const { t } = useI18n();
  const [tab, setTab] = useState("text");
  const [text, setText] = useState("");
  const [json, setJson] = useState("");

  const [services, setServices] = useState([]);
  const [servicesReal, setServicesReal] = useState(false);
  const [selected, setSelected] = useState(() => new Set());

  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [group, setGroup] = useState(null);
  const [runs, setRuns] = useState([]);
  const [mockResult, setMockResult] = useState(null);

  const pollRef = useRef(null);
  const cancelRef = useRef(false);

  // Load available services (fall back to mock data when the API is down).
  useEffect(() => {
    let active = true;
    getServices()
      .then((data) => {
        if (!active) return;
        const list = Array.isArray(data) && data.length ? data : MOCK_SERVICES;
        const real = Array.isArray(data) && data.length > 0;
        setServices(list);
        setServicesReal(real);
        setSelected(new Set(list.map((s) => s.id)));
      })
      .catch(() => {
        if (!active) return;
        setServices(MOCK_SERVICES);
        setServicesReal(false);
        setSelected(new Set(MOCK_SERVICES.map((s) => s.id)));
      });
    return () => {
      active = false;
    };
  }, []);

  // Stop polling on unmount.
  useEffect(
    () => () => {
      cancelRef.current = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    },
    []
  );

  const currentValue = tab === "json" ? json : text;
  const hasInput = currentValue.trim().length > 0;
  const canAnalyze = hasInput && selected.size > 0 && !running;

  const consolidated = useMemo(() => consolidate(runs), [runs]);
  const doneCount = runs.filter((r) => TERMINAL.has(r.task?.status)).length;

  const toggleService = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(services.map((s) => s.id)));
  const clearAll = () => setSelected(new Set());

  const startPolling = (childRuns) => {
    const ids = childRuns.map((r) => r.task.id);
    let attempts = 0;
    const tick = async () => {
      if (cancelRef.current) return;
      attempts += 1;
      const tasks = await Promise.all(
        ids.map((id) => getTask(id).catch(() => null))
      );
      setRuns((prev) =>
        prev.map((run) => {
          const fresh = tasks.find((tk) => tk && tk.id === run.task.id);
          return fresh ? { ...run, task: fresh } : run;
        })
      );
      const allDone = tasks.every((tk) => tk && TERMINAL.has(tk.status));
      if (allDone || attempts >= MAX_POLLS) {
        setRunning(false);
        return;
      }
      pollRef.current = setTimeout(tick, POLL_INTERVAL);
    };
    tick();
  };

  const analyze = async () => {
    setError(null);
    setGroup(null);
    setRuns([]);
    setMockResult(null);
    if (pollRef.current) clearTimeout(pollRef.current);

    let inputData;
    try {
      inputData = buildInputData(tab, text, json);
    } catch {
      setError(t("analyze.error.json"));
      return;
    }

    const chosen = services.filter((s) => selected.has(s.id));
    if (chosen.length === 0) {
      setError(t("analyze.services.none"));
      return;
    }

    setRunning(true);

    // Without real services we can't dispatch tasks: run the mock scanner.
    if (!servicesReal) {
      try {
        const joined = inputData.pages.map((p) => p.content).join("\n\n");
        setMockResult(await mockAnalyze(joined));
      } catch (err) {
        setError(err.message || t("analyze.error.generic"));
      } finally {
        setRunning(false);
      }
      return;
    }

    try {
      // 1) Create the parent "group" task (no service of its own).
      const parent = await submitTask({ userId: USER_ID, inputData });
      setGroup(parent);

      // 2) Fan out one child task per selected service.
      const children = await Promise.all(
        chosen.map((svc) =>
          submitTask({
            userId: USER_ID,
            inputData,
            serviceId: svc.id,
            parentTaskId: parent.id,
          }).then((task) => ({ service: svc, task }))
        )
      );
      setRuns(children);

      // 3) Poll children for intermediate + final results.
      cancelRef.current = false;
      startPolling(children);
    } catch (err) {
      setError(err.message || t("analyze.error.generic"));
      setRunning(false);
    }
  };

  const onKeyDown = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && canAnalyze) {
      analyze();
    }
  };

  const result = mockResult ?? consolidated;
  const showLoading = running && !result;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Left: input + service selection */}
      <Card>
        <CardHeader>
          <CardTitle>{t("analyze.input.title")}</CardTitle>
          <CardDescription>{t("analyze.input.desc")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="w-full">
              <TabsTrigger value="text" className="flex-1">
                <FileText className="h-4 w-4" /> {t("analyze.tab.text")}
              </TabsTrigger>
              <TabsTrigger value="json" className="flex-1">
                <Braces className="h-4 w-4" /> {t("analyze.tab.json")}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="text">
              <Textarea
                rows={10}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={t("analyze.text.placeholder")}
                className="font-sans"
              />
            </TabsContent>

            <TabsContent value="json">
              <Textarea
                rows={10}
                value={json}
                onChange={(e) => setJson(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={
                  '{\n  "metadata": {},\n  "pages": [\n    { "content": "…", "page_number": 1 }\n  ]\n}'
                }
              />
            </TabsContent>
          </Tabs>

          {/* Service selection */}
          <div className="mt-5">
            <div className="mb-2 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">
                  {t("analyze.services.title")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("analyze.services.desc")}
                </p>
              </div>
              <div className="flex gap-2 text-xs">
                <button
                  type="button"
                  onClick={selectAll}
                  className="text-muted-foreground hover:text-foreground"
                >
                  {t("analyze.services.all")}
                </button>
                <span className="text-border">·</span>
                <button
                  type="button"
                  onClick={clearAll}
                  className="text-muted-foreground hover:text-foreground"
                >
                  {t("analyze.services.clear")}
                </button>
              </div>
            </div>

            {services.length === 0 ? (
              <p className="rounded-lg border border-border bg-background/40 p-3 text-xs text-muted-foreground">
                {t("analyze.services.empty")}
              </p>
            ) : (
              <div className="flex max-h-44 flex-col gap-1.5 overflow-y-auto pr-1">
                {services.map((svc) => {
                  const checked = selected.has(svc.id);
                  return (
                    <label
                      key={svc.id}
                      className={cn(
                        "flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 text-sm transition-colors",
                        checked
                          ? "border-primary/50 bg-primary/5"
                          : "border-border bg-background/40 hover:border-border"
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleService(svc.id)}
                        className="h-4 w-4 accent-primary"
                      />
                      <span className="flex-1 truncate font-medium">
                        {svc.name}
                      </span>
                      <Badge variant="muted">
                        {t(`service.type.${svc.type}`)}
                      </Badge>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          <div className="mt-4 flex items-center gap-3">
            <Button onClick={analyze} disabled={!canAnalyze}>
              {running ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {running
                ? t("analyze.running")
                : t("analyze.run.group").replace("{n}", selected.size)}
            </Button>
            <span className="text-xs text-muted-foreground">
              {t("analyze.shortcut")}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Right: group progress + consolidated results */}
      <Card>
        <CardHeader>
          <CardTitle>{t("analyze.results.title")}</CardTitle>
          <CardDescription>{t("analyze.results.desc")}</CardDescription>
        </CardHeader>
        <CardContent>
          {runs.length > 0 && (
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
                  {t("task.id")} :{" "}
                  <code className="text-foreground">{group.id}</code>
                </div>
              )}
              <div className="flex flex-col gap-2">
                {runs.map((run) => (
                  <ServiceRunRow key={run.task.id} run={run} t={t} />
                ))}
              </div>
            </div>
          )}
          <Results result={result} loading={showLoading} error={error} />
        </CardContent>
      </Card>
    </div>
  );
}
