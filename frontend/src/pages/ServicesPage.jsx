import {
  Server,
  CheckCircle2,
  XCircle,
  Loader2,
  Circle,
  AlertTriangle,
  CornerDownRight,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { cn } from "../lib/utils";
import { SERVICES, TASKS } from "../lib/mockData";

const STATUS = {
  pending: {
    label: "En attente",
    badge: "muted",
    icon: Circle,
    color: "text-muted-foreground",
  },
  running: {
    label: "En cours",
    badge: "default",
    icon: Loader2,
    color: "text-primary",
    spin: true,
  },
  success: {
    label: "Succès",
    badge: "success",
    icon: CheckCircle2,
    color: "text-success",
  },
  error: {
    label: "Erreur",
    badge: "destructive",
    icon: XCircle,
    color: "text-destructive",
  },
};

function StatusIcon({ status }) {
  const meta = STATUS[status] || STATUS.pending;
  const Icon = meta.icon;
  return (
    <Icon className={cn("h-4 w-4 shrink-0", meta.color, meta.spin && "animate-spin")} />
  );
}

function TaskNode({ task, byId, depth }) {
  const meta = STATUS[task.status] || STATUS.pending;
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
          <StatusIcon status={task.status} />
          <span className="font-mono text-sm font-medium">{task.id}</span>
          <code className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
            {task.route}
          </code>
          <Badge variant="muted">{task.service}</Badge>
          <Badge variant={meta.badge} className="ml-auto">
            {meta.label}
          </Badge>
        </div>
        {task.error && (
          <div className="flex items-start gap-2 rounded-md bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{task.error}</span>
          </div>
        )}
      </div>

      {(task.children || []).map((childId) => {
        const child = byId[childId];
        if (!child) return null;
        return (
          <div key={childId} className="mt-2">
            <TaskNode task={child} byId={byId} depth={depth + 1} />
          </div>
        );
      })}
    </div>
  );
}

export default function ServicesPage() {
  const byId = Object.fromEntries(TASKS.map((t) => [t.id, t]));
  const childIds = new Set(TASKS.flatMap((t) => t.children || []));
  const roots = TASKS.filter((t) => !childIds.has(t.id));

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      {/* Services */}
      <Card className="h-fit">
        <CardHeader>
          <CardTitle>Services</CardTitle>
          <CardDescription>État des workers connectés.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {SERVICES.map((svc) => (
            <div
              key={svc.name}
              className="flex items-start gap-3 rounded-lg border border-border bg-background/40 p-3"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/15">
                <Server className="h-4 w-4 text-primary" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{svc.name}</span>
                  <Badge
                    variant={
                      svc.status === "online"
                        ? "success"
                        : svc.status === "degraded"
                          ? "default"
                          : "destructive"
                    }
                  >
                    {svc.status}
                  </Badge>
                </div>
                <div className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                  <div>in : {svc.in_queue}</div>
                  <div>out : {svc.out_queue}</div>
                  <div>quota : {svc.quotas}</div>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Tasks / execution graph */}
      <Card>
        <CardHeader>
          <CardTitle>Graphe d'exécution</CardTitle>
          <CardDescription>
            Suivi des tâches et de leurs sous-tâches (id, route, statut).
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {roots.map((root) => (
            <TaskNode key={root.id} task={root} byId={byId} depth={0} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
