import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Clock, AlertTriangle, CheckCircle, Loader2, RefreshCw, Trash2, Play } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { getMyTasks, deleteTask, retryTask } from "../lib/api";
import { useI18n } from "../lib/i18n.jsx";
import { formatDuration } from "../lib/runModel";

const STATUS_CONFIG = {
  pending: { icon: Clock, variant: "secondary", labelKey: "task.status.pending" },
  running: { icon: Loader2, variant: "default", labelKey: "task.status.running" },
  success: { icon: CheckCircle, variant: "outline", labelKey: "task.status.success" },
  error: { icon: AlertTriangle, variant: "destructive", labelKey: "task.status.error" },
  revoked: { icon: Trash2, variant: "muted", labelKey: "task.status.revoked" },
};

function StatusBadge({ status }) {
  const { t } = useI18n();
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  const Icon = config.icon;
  return (
    <Badge variant={config.variant} className="gap-1">
      <Icon className="h-3 w-3" />
      {t(config.labelKey)}
    </Badge>
  );
}

export default function MyTasksPage() {
  const { t } = useI18n();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const loadTasks = useCallback(() => {
    setLoading(true);
    const params = { rootsOnly: true, ...(filter !== "all" ? { status: filter } : {}) };
    getMyTasks(params)
      .then((page) => setTasks(page.items || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filter]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const handleDelete = async (taskId) => {
    if (!confirm(t("task.confirmDelete"))) return;
    try {
      await deleteTask(taskId);
      loadTasks();
    } catch (err) {
      console.error(err);
      alert(t("task.deleteError"));
    }
  };

  const handleRetry = async (taskId) => {
    try {
      await retryTask(taskId);
      loadTasks();
    } catch (err) {
      console.error(err);
      alert(t("task.retryError"));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">{t("nav.myTasks")}</h2>
          <p className="text-sm text-muted-foreground">{t("myTasks.subtitle")}</p>
        </div>
        <Button variant="outline" size="sm" onClick={loadTasks}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {t("common.refresh")}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("myTasks.filters")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            {["all", "pending", "running", "success", "error"].map((s) => (
              <Button
                key={s}
                variant={filter === s ? "default" : "outline"}
                size="sm"
                onClick={() => setFilter(s)}
              >
                {t(`task.status.${s}`)}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("myTasks.tasks")}</CardTitle>
          <CardDescription>{t("myTasks.tasksDescription")}</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : tasks.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              {t("myTasks.noTasks")}
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("myTasks.id")}</TableHead>
                  <TableHead>{t("myTasks.source")}</TableHead>
                  <TableHead>{t("myTasks.status")}</TableHead>
                  <TableHead>{t("myTasks.progress")}</TableHead>
                  <TableHead>{t("myTasks.duration")}</TableHead>
                  <TableHead>{t("myTasks.created")}</TableHead>
                  <TableHead className="text-right">{t("myTasks.actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((task) => (
                  <TableRow key={task.id}>
                    <TableCell>
                      <Link
                        to={`/analysis/${task.id}`}
                        className="font-medium hover:underline"
                      >
                        {task.id.slice(0, 8)}...
                      </Link>
                    </TableCell>
                    <TableCell>
                      {task.input_data?.source ? t(`wiz.source.kind.${task.input_data.source}`) : "-"}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={task.status} />
                    </TableCell>
                    <TableCell>{task.progress}%</TableCell>
                    <TableCell>
                      {task.duration_seconds != null ? formatDuration(task.duration_seconds) : "-"}
                    </TableCell>
                    <TableCell>
                      {new Date(task.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        {task.status === "error" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRetry(task.id)}
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(task.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}