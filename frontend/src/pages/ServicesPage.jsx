import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Server,
  CheckCircle2,
  XCircle,
  Loader2,
  Circle,
  AlertTriangle,
  CornerDownRight,
  Search,
  Ban,
  RotateCcw,
  ChevronRight,
  Eye,
} from "lucide-react";import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Dialog } from "../components/ui/dialog";
import { cn } from "../lib/utils";
import { SERVICES, TASKS } from "../lib/mockData";
import { getServices, getTasks, revokeTask, retryTask } from "../lib/api";
import { useI18n } from "../lib/i18n.jsx";

// Backend tasks are a flat list (id, parent_task_id, service_id, status, …).
// Turn them into the node shape the UI expects: a `children` array of ids,
// a human `route`, and a resolved `service` name.
function normalizeTasks(rawTasks, services) {
  const svcById = new Map(services.map((s) => [s.id, s]));
  const childrenOf = new Map();
  for (const task of rawTasks) {
    if (task.parent_task_id) {
      if (!childrenOf.has(task.parent_task_id))
        childrenOf.set(task.parent_task_id, []);
      childrenOf.get(task.parent_task_id).push(task.id);
    }
  }
  return rawTasks.map((task) => {
    const svc = task.service_id ? svcById.get(task.service_id) : null;
    return {
      ...task,
      children: childrenOf.get(task.id) || [],
      service: svc?.name ?? (task.service_id ? task.service_id.slice(0, 8) : "group"),
      route: svc ? `/${svc.name}` : "/group",
    };
  });
}

const STATUS = {
  pending: {
    key: "status.pending",
    badge: "muted",
    icon: Circle,
    color: "text-muted-foreground",
  },
  running: {
    key: "status.running",
    badge: "default",
    icon: Loader2,
    color: "text-primary",
    spin: true,
  },
  success: {
    key: "status.success",
    badge: "success",
    icon: CheckCircle2,
    color: "text-success",
  },
  error: {
    key: "status.error",
    badge: "destructive",
    icon: XCircle,
    color: "text-destructive",
  },
  revoked: {
    key: "status.revoked",
    badge: "muted",
    icon: Ban,
    color: "text-muted-foreground",
  },
};

function StatusIcon({ status }) {
  const meta = STATUS[status] || STATUS.pending;
  const Icon = meta.icon;
  return (
    <Icon className={cn("h-4 w-4 shrink-0", meta.color, meta.spin && "animate-spin")} />
  );
}

function TaskNode({ task, byId, depth, onRevoke, onRetry }) {
  const { t } = useI18n();
  const meta = STATUS[task.status] || STATUS.pending;
  const canRevoke = task.status !== "success" && task.status !== "error";
  const canRetry = task.status === "error";
  const children = (task.children || [])
    .map((childId) => byId[childId])
    .filter(Boolean);
  const hasChildren = children.length > 0;
  const [open, setOpen] = useState(true);
  return (
    <div>
      <div
        className={cn(
          "flex flex-col gap-2 rounded-lg border p-3",
          task.status === "error"
            ? "border-destructive/50 bg-destructive/5"
            : "border-border bg-background/40"
        )}
        style={{ marginLeft: depth * 24 }}
      >
        <div className="flex items-center gap-2">
          {depth > 0 && (
            <CornerDownRight className="h-4 w-4 text-muted-foreground" />
          )}
          {hasChildren ? (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label={open ? t("task.collapse") : t("task.expand")}
            >
              <ChevronRight
                className={cn(
                  "h-4 w-4 transition-transform",
                  open && "rotate-90"
                )}
              />
            </button>
          ) : (
            <span className="w-5" />
          )}
          <StatusIcon status={task.status} />
          <span className="font-mono text-sm font-medium">{task.id}</span>
          <code className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
            {task.route}
          </code>
          <Badge variant="muted">{task.service}</Badge>
          {hasChildren && (
            <Badge variant="muted">
              {t("task.subtasks").replace("{n}", children.length)}
            </Badge>
          )}
          <Badge variant={meta.badge} className="ml-auto">
            {t(meta.key)}
          </Badge>
        </div>
        {task.error && (
          <div className="flex items-start gap-2 rounded-md bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{task.error}</span>
          </div>
        )}
        {(canRevoke || canRetry) && (
          <div className="flex justify-end gap-2">
            {canRetry && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onRetry(task.id)}
              >
                <RotateCcw className="h-3.5 w-3.5" />
                {t("task.retry")}
              </Button>
            )}
            {canRevoke && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onRevoke(task.id)}
              >
                <Ban className="h-3.5 w-3.5" />
                {t("task.revoke")}
              </Button>
            )}
          </div>
        )}
        {task.status === "success" && depth === 0 && (
          <div className="flex justify-end">
            <Link
              to={`/analysis/${task.id}`}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-input bg-transparent px-3 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              <Eye className="h-3.5 w-3.5" />
              {t("task.view")}
            </Link>
          </div>
        )}
      </div>

      {hasChildren &&
        open &&
        children.map((child) => (
          <div key={child.id} className="mt-2">
            <TaskNode
              task={child}
              byId={byId}
              depth={depth + 1}
              onRevoke={onRevoke}
              onRetry={onRetry}
            />
          </div>
        ))}
    </div>
  );
}

const SERVICE_TYPE_VARIANT = {
  guard: "default",
  analyser: "success",
  other: "muted",
};

function ServiceCard({ svc, onClick }) {
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-start gap-3 rounded-lg border border-border bg-background/40 p-3 text-left transition-colors hover:bg-background/70"
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/15">
        <Server className="h-4 w-4 text-primary" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2 font-medium">
            <span className="truncate">{svc.name}</span>
            <code className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
              v{svc.version}
            </code>
          </span>
          <Badge variant={SERVICE_TYPE_VARIANT[svc.type] ?? "muted"}>
            {t(`service.type.${svc.type}`)}
          </Badge>
        </div>
        {svc.description && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {svc.description}
          </p>
        )}
        {svc.tags?.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {svc.tags.map((tag) => (
              <Badge key={tag} variant="muted">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </button>
  );
}

function SchemaBlock({ title, schema }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <pre className="max-h-48 overflow-auto rounded-lg border border-border bg-background/60 p-3 text-xs text-foreground">
        {JSON.stringify(schema ?? {}, null, 2)}
      </pre>
    </div>
  );
}

function ServiceDialog({ svc, open, onClose }) {
  const { t } = useI18n();
  if (!svc) return null;
  return (
    <Dialog open={open} onClose={onClose} title={svc.name} icon={Server}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={SERVICE_TYPE_VARIANT[svc.type] ?? "muted"}>
            {t(`service.type.${svc.type}`)}
          </Badge>
          <code className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
            v{svc.version}
          </code>
        </div>

        {svc.description && (
          <p className="text-sm text-muted-foreground">{svc.description}</p>
        )}

        {svc.tags?.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {svc.tags.map((tag) => (
              <Badge key={tag} variant="muted">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        <SchemaBlock title={t("service.inputSchema")} schema={svc.input_schema} />
        <SchemaBlock title={t("service.outputSchema")} schema={svc.output_schema} />

        <dl className="grid grid-cols-1 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-2">
          <div className="flex items-baseline justify-between gap-2 border-b border-border/60 pb-1">
            <dt className="text-muted-foreground">{t("service.id")}</dt>
            <dd className="truncate text-right font-mono text-foreground">{svc.id}</dd>
          </div>
          {svc.created_at && (
            <div className="flex items-baseline justify-between gap-2 border-b border-border/60 pb-1">
              <dt className="text-muted-foreground">{t("service.created")}</dt>
              <dd className="text-right text-foreground">
                {new Date(svc.created_at).toLocaleString()}
              </dd>
            </div>
          )}
          {svc.updated_at && (
            <div className="flex items-baseline justify-between gap-2 border-b border-border/60 pb-1">
              <dt className="text-muted-foreground">{t("service.updated")}</dt>
              <dd className="text-right text-foreground">
                {new Date(svc.updated_at).toLocaleString()}
              </dd>
            </div>
          )}
        </dl>
      </div>
    </Dialog>
  );
}

export default function ServicesPage() {
  const { t } = useI18n();
  const [services, setServices] = useState(SERVICES);
  const [tasks, setTasks] = useState(TASKS);
  const [tasksReal, setTasksReal] = useState(false);
  const byId = Object.fromEntries(tasks.map((task) => [task.id, task]));
  const childIds = new Set(tasks.flatMap((task) => task.children || []));
  const roots = tasks.filter((task) => !childIds.has(task.id));
  const [taskQuery, setTaskQuery] = useState("");

  // Load services then tasks from the backend (fallback to mock when down).
  useEffect(() => {
    let cancelled = false;
    let svcList = SERVICES;
    getServices()
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) svcList = data;
        if (!cancelled) setServices(svcList);
        return getTasks();
      })
      .then((rawTasks) => {
        if (cancelled) return;
        if (Array.isArray(rawTasks) && rawTasks.length > 0) {
          setTasks(normalizeTasks(rawTasks, svcList));
          setTasksReal(true);
        }
      })
      .catch(() => {
        /* keep mock fallback when the API is unreachable */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Once connected to the backend, refresh the graph periodically so task
  // status/progress (including rolled-up parent "group" tasks) update live.
  useEffect(() => {
    if (!tasksReal) return undefined;
    let cancelled = false;
    const id = setInterval(() => {
      getTasks()
        .then((rawTasks) => {
          if (cancelled || !Array.isArray(rawTasks)) return;
          setServices((svc) => {
            setTasks(normalizeTasks(rawTasks, svc));
            return svc;
          });
        })
        .catch(() => {
          /* ignore transient errors during polling */
        });
    }, 2500);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [tasksReal]);

  const matchesTask = (task, q) =>
    task.id?.toLowerCase().includes(q) ||
    task.route?.toLowerCase().includes(q) ||
    task.service?.toLowerCase().includes(q) ||
    task.status?.toLowerCase().includes(q);

  const filteredRoots = useMemo(() => {
    const q = taskQuery.trim().toLowerCase();
    if (!q) return roots;
    const matchTree = (task) => {
      if (matchesTask(task, q)) return true;
      return (task.children || []).some((cid) => {
        const child = byId[cid];
        return child && matchTree(child);
      });
    };
    return roots.filter(matchTree);
  }, [roots, byId, taskQuery]);

  const handleRevoke = async (id) => {
    if (tasksReal) {
      try {
        const updated = await revokeTask(id);
        setTasks((prev) =>
          prev.map((task) =>
            task.id === id ? { ...task, ...updated } : task
          )
        );
        return;
      } catch {
        /* fall through to optimistic update */
      }
    }
    setTasks((prev) =>
      prev.map((task) =>
        task.id === id ? { ...task, status: "revoked", error: null } : task
      )
    );
  };

  const handleRetry = async (id) => {
    if (tasksReal) {
      try {
        const updated = await retryTask(id);
        setTasks((prev) =>
          prev.map((task) =>
            task.id === id ? { ...task, ...updated } : task
          )
        );
        return;
      } catch {
        /* fall through to optimistic update */
      }
    }
    setTasks((prev) =>
      prev.map((task) =>
        task.id === id ? { ...task, status: "running", error: null } : task
      )
    );
  };

  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return services;
    return services.filter(
      (s) =>
        s.name?.toLowerCase().includes(q) ||
        s.type?.toLowerCase().includes(q) ||
        (s.tags || []).some((tag) => tag.toLowerCase().includes(q))
    );
  }, [services, query]);

  return (
    <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
      {/* Services */}
      <Card className="h-fit">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            {t("services.title")}
            <Badge variant="muted">{services.length}</Badge>
          </CardTitle>
          <CardDescription>{t("services.desc")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("services.search")}
              className="pl-9"
            />
          </div>
          <div className="flex max-h-[70vh] flex-col gap-3 overflow-y-auto pr-1">
            {filtered.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {t("services.empty")}
              </p>
            ) : (
              filtered.map((svc) => (
                <ServiceCard
                  key={svc.id}
                  svc={svc}
                  onClick={() => setSelected(svc)}
                />
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Tasks / execution graph */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            {t("graph.title")}
            <Badge variant="muted">{tasks.length}</Badge>
          </CardTitle>
          <CardDescription>{t("graph.desc")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={taskQuery}
              onChange={(e) => setTaskQuery(e.target.value)}
              placeholder={t("graph.search")}
              className="pl-9"
            />
          </div>
          <div className="flex max-h-[70vh] flex-col gap-3 overflow-y-auto pr-1">
            {filteredRoots.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {t("graph.empty")}
              </p>
            ) : (
              filteredRoots.map((root) => (
                <TaskNode
                  key={root.id}
                  task={root}
                  byId={byId}
                  depth={0}
                  onRevoke={handleRevoke}
                  onRetry={handleRetry}
                />
              ))
            )}
          </div>
        </CardContent>
      </Card>

      <ServiceDialog
        svc={selected}
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
