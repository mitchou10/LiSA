import { useCallback, useEffect, useMemo, useState } from "react";
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
  Trash2,
  ChevronLeft,
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
import {
  getServicesPage,
  getServices,
  getTasksPage,
  getTaskChildren,
  revokeTask,
  retryTask,
  deleteTask,
} from "../lib/api";
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

function TaskNode({ task, byId, depth, onRevoke, onRetry, onDelete }) {
  const { t } = useI18n();
  const meta = STATUS[task.status] || STATUS.pending;
  const canRevoke = task.status !== "success" && task.status !== "error";
  const canRetry = task.status === "error";
  const canDelete =
    task.status === "success" ||
    task.status === "error" ||
    task.status === "revoked";
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
        {(canRevoke || canRetry || canDelete) && (
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
            {canDelete && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onDelete(task.id)}
                className="text-destructive hover:bg-destructive/10 hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
                {t("task.delete")}
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
              onDelete={onDelete}
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

const SERVICE_PAGE_SIZE = 10;
const TASK_PAGE_SIZE = 10;
const SERVICE_TYPE_OPTIONS = ["guard", "analyser", "other"];
const TASK_STATUS_OPTIONS = [
  "pending",
  "running",
  "success",
  "error",
  "revoked",
];

function FilterSelect({ value, onChange, ariaLabel, children }) {
  return (
    <select
      aria-label={ariaLabel}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 rounded-md border border-input bg-transparent px-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
    >
      {children}
    </select>
  );
}

function Pager({ offset, limit, total, onPrev, onNext }) {
  const { t } = useI18n();
  const page = Math.floor(offset / limit) + 1;
  const pageCount = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
      <span>{t("pagination.total").replace("{n}", total)}</span>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onPrev}
          disabled={offset <= 0}
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          {t("pagination.prev")}
        </Button>
        <span className="tabular-nums">
          {t("pagination.page")
            .replace("{page}", page)
            .replace("{total}", pageCount)}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={onNext}
          disabled={offset + limit >= total}
        >
          {t("pagination.next")}
          <ChevronRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

export default function ServicesPage() {
  const { t } = useI18n();

  // Full service list (mock fallback + name resolution + filter dropdown).
  const [allServices, setAllServices] = useState(SERVICES);

  // Services panel (server-side paginated + filtered).
  const [services, setServices] = useState(SERVICES);
  const [serviceTotal, setServiceTotal] = useState(SERVICES.length);
  const [serviceOffset, setServiceOffset] = useState(0);
  const [serviceQuery, setServiceQuery] = useState("");
  const [serviceType, setServiceType] = useState("");
  const [servicesReal, setServicesReal] = useState(false);

  // Tasks panel (server-side paginated + filtered).
  const [tasks, setTasks] = useState(TASKS);
  const [taskTotal, setTaskTotal] = useState(TASKS.length);
  const [taskOffset, setTaskOffset] = useState(0);
  const [taskStatus, setTaskStatus] = useState("");
  const [taskServiceId, setTaskServiceId] = useState("");
  const [taskQuery, setTaskQuery] = useState("");
  const [tasksReal, setTasksReal] = useState(false);

  const [selected, setSelected] = useState(null);

  const byId = Object.fromEntries(tasks.map((task) => [task.id, task]));
  const childIds = new Set(tasks.flatMap((task) => task.children || []));
  const roots = tasks.filter((task) => !childIds.has(task.id));

  // Load the full service list once (for name resolution + dropdowns).
  useEffect(() => {
    let cancelled = false;
    getServices()
      .then((data) => {
        if (!cancelled && Array.isArray(data) && data.length > 0)
          setAllServices(data);
      })
      .catch(() => {
        /* keep mock fallback */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Services panel: fetch a filtered page from the backend.
  useEffect(() => {
    let cancelled = false;
    getServicesPage({
      q: serviceQuery || undefined,
      type: serviceType || undefined,
      limit: SERVICE_PAGE_SIZE,
      offset: serviceOffset,
    })
      .then((page) => {
        if (cancelled) return;
        setServices(page.items ?? []);
        setServiceTotal(page.total ?? 0);
        setServicesReal(true);
      })
      .catch(() => {
        if (cancelled) return;
        setServicesReal(false);
        const q = serviceQuery.trim().toLowerCase();
        const list = SERVICES.filter(
          (s) =>
            (!serviceType || s.type === serviceType) &&
            (!q ||
              s.name?.toLowerCase().includes(q) ||
              (s.tags || []).some((tag) => tag.toLowerCase().includes(q)))
        );
        setServices(list);
        setServiceTotal(list.length);
      });
    return () => {
      cancelled = true;
    };
  }, [serviceQuery, serviceType, serviceOffset]);

  // Whether any task filter is active: drives roots-only vs. flat listing.
  const filtersActive = Boolean(taskStatus || taskServiceId);

  // Load a page of tasks. Without filters we paginate root tasks and expand
  // their children to render the full tree; with filters we list the matching
  // tasks flat (each shown as its own root).
  const loadTasks = useCallback(async () => {
    const rootsOnly = !filtersActive;
    const page = await getTasksPage({
      status: taskStatus || undefined,
      serviceId: taskServiceId || undefined,
      rootsOnly,
      limit: TASK_PAGE_SIZE,
      offset: taskOffset,
    });
    const items = page.items ?? [];
    let flat = items;
    if (rootsOnly) {
      const childArrays = await Promise.all(
        items.map((r) => getTaskChildren(r.id).catch(() => []))
      );
      flat = [...items, ...childArrays.flat()];
    }
    return { flat, total: page.total ?? 0 };
  }, [filtersActive, taskStatus, taskServiceId, taskOffset]);

  // Tasks panel: fetch the current page (fallback to mock when API is down).
  useEffect(() => {
    let cancelled = false;
    loadTasks()
      .then(({ flat, total }) => {
        if (cancelled) return;
        setTasks(normalizeTasks(flat, allServices));
        setTaskTotal(total);
        setTasksReal(true);
      })
      .catch(() => {
        if (cancelled) return;
        setTasksReal(false);
        setTasks(TASKS);
        setTaskTotal(TASKS.length);
      });
    return () => {
      cancelled = true;
    };
  }, [loadTasks, allServices]);

  // Refresh the current task page periodically so status/progress stay live.
  useEffect(() => {
    if (!tasksReal) return undefined;
    let cancelled = false;
    const id = setInterval(() => {
      loadTasks()
        .then(({ flat, total }) => {
          if (cancelled) return;
          setTasks(normalizeTasks(flat, allServices));
          setTaskTotal(total);
        })
        .catch(() => {
          /* ignore transient polling errors */
        });
    }, 2500);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [tasksReal, loadTasks, allServices]);

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
          prev.map((task) => (task.id === id ? { ...task, ...updated } : task))
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
          prev.map((task) => (task.id === id ? { ...task, ...updated } : task))
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

  const handleDelete = async (id) => {
    if (tasksReal) {
      try {
        await deleteTask(id);
        const { flat, total } = await loadTasks();
        setTasks(normalizeTasks(flat, allServices));
        setTaskTotal(total);
        return;
      } catch {
        /* fall through to optimistic removal */
      }
    }
    setTasks((prev) => prev.filter((task) => task.id !== id));
    setTaskTotal((n) => Math.max(0, n - 1));
  };

  const resetServiceFilter = (fn) => {
    fn();
    setServiceOffset(0);
  };
  const resetTaskFilter = (fn) => {
    fn();
    setTaskOffset(0);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
      {/* Services */}
      <Card className="h-fit">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            {t("services.title")}
            <Badge variant="muted">{serviceTotal}</Badge>
          </CardTitle>
          <CardDescription>{t("services.desc")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={serviceQuery}
              onChange={(e) =>
                resetServiceFilter(() => setServiceQuery(e.target.value))
              }
              placeholder={t("services.search")}
              className="pl-9"
            />
          </div>
          <FilterSelect
            value={serviceType}
            onChange={(v) => resetServiceFilter(() => setServiceType(v))}
            ariaLabel={t("filter.type")}
          >
            <option value="">{t("filter.type.all")}</option>
            {SERVICE_TYPE_OPTIONS.map((type) => (
              <option key={type} value={type}>
                {t(`service.type.${type}`)}
              </option>
            ))}
          </FilterSelect>
          <div className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto pr-1">
            {services.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {t("services.empty")}
              </p>
            ) : (
              services.map((svc) => (
                <ServiceCard
                  key={svc.id}
                  svc={svc}
                  onClick={() => setSelected(svc)}
                />
              ))
            )}
          </div>
          {servicesReal && serviceTotal > SERVICE_PAGE_SIZE && (
            <Pager
              offset={serviceOffset}
              limit={SERVICE_PAGE_SIZE}
              total={serviceTotal}
              onPrev={() =>
                setServiceOffset((o) => Math.max(0, o - SERVICE_PAGE_SIZE))
              }
              onNext={() => setServiceOffset((o) => o + SERVICE_PAGE_SIZE)}
            />
          )}
        </CardContent>
      </Card>

      {/* Tasks / execution graph */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            {t("graph.title")}
            <Badge variant="muted">{taskTotal}</Badge>
          </CardTitle>
          <CardDescription>{t("graph.desc")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={taskQuery}
                onChange={(e) => setTaskQuery(e.target.value)}
                placeholder={t("graph.search")}
                className="pl-9"
              />
            </div>
            <FilterSelect
              value={taskStatus}
              onChange={(v) => resetTaskFilter(() => setTaskStatus(v))}
              ariaLabel={t("filter.status")}
            >
              <option value="">{t("filter.status.all")}</option>
              {TASK_STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {t(`status.${status}`)}
                </option>
              ))}
            </FilterSelect>
            <FilterSelect
              value={taskServiceId}
              onChange={(v) => resetTaskFilter(() => setTaskServiceId(v))}
              ariaLabel={t("filter.service")}
            >
              <option value="">{t("filter.service.all")}</option>
              {allServices.map((svc) => (
                <option key={svc.id} value={svc.id}>
                  {svc.name}
                </option>
              ))}
            </FilterSelect>
          </div>
          <div className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto pr-1">
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
                  onDelete={handleDelete}
                />
              ))
            )}
          </div>
          {tasksReal && taskTotal > TASK_PAGE_SIZE && (
            <Pager
              offset={taskOffset}
              limit={TASK_PAGE_SIZE}
              total={taskTotal}
              onPrev={() =>
                setTaskOffset((o) => Math.max(0, o - TASK_PAGE_SIZE))
              }
              onNext={() => setTaskOffset((o) => o + TASK_PAGE_SIZE)}
            />
          )}
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
