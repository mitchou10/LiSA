import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Users,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { cn } from "../lib/utils";
import { getDashboardStats } from "../lib/api";
import { mockDashboardStats } from "../lib/mockDashboard";
import { useI18n } from "../lib/i18n.jsx";

const RANGES = [
  { days: 7, labelKey: "dashboard.range.7" },
  { days: 30, labelKey: "dashboard.range.30" },
  { days: 90, labelKey: "dashboard.range.90" },
];

const COLOR_PRIMARY = "hsl(217 91% 60%)";
const COLOR_FLAGGED = "hsl(0 84% 64%)";
const SEVERITY_COLORS = {
  high: "hsl(0 84% 64%)",
  medium: "hsl(38 92% 50%)",
  low: "hsl(142 60% 48%)",
};

function severityVariant(severity) {
  if (severity === "high") return "destructive";
  if (severity === "medium") return "default";
  return "muted";
}

function shortDay(iso) {
  // iso is YYYY-MM-DD; show MM-DD for a compact axis.
  return iso?.slice(5) ?? iso;
}

function KpiCard({ icon: Icon, label, value, accent }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div
          className={cn(
            "flex h-11 w-11 items-center justify-center rounded-lg",
            accent
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-2xl font-semibold leading-tight">{value}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { t } = useI18n();
  const [userId, setUserId] = useState("");
  const [userInput, setUserInput] = useState("");
  const [days, setDays] = useState(30);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDashboardStats({
        userId: userId || undefined,
        days,
      });
      setStats(data);
    } catch (err) {
      // Backend unavailable → fall back to mock data so the dashboard is
      // still explorable in dev mode.
      try {
        const mock = mockDashboardStats({ userId: userId || undefined, days });
        setStats(mock);
      } catch {
        setError(err?.message || t("dashboard.error"));
        setStats(null);
      }
    } finally {
      setLoading(false);
    }
  }, [userId, days, t]);

  useEffect(() => {
    load();
  }, [load]);

  const typeData = useMemo(
    () =>
      (stats?.by_type ?? []).map((d) => ({
        ...d,
        label: t(`detection.${d.type}`) || d.type,
      })),
    [stats, t]
  );

  const hasData =
    stats && (stats.total_detections > 0 || stats.total_tasks > 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">{t("dashboard.title")}</h2>
          <p className="text-sm text-muted-foreground">{t("dashboard.desc")}</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setUserId(userInput.trim());
            }}
          >
            <Users className="h-4 w-4 text-muted-foreground" />
            <Input
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              placeholder={t("dashboard.user.placeholder")}
              className="w-64"
            />
          </form>

          <div className="flex items-center gap-1 rounded-lg bg-muted p-1">
            {RANGES.map((r) => (
              <button
                key={r.days}
                type="button"
                onClick={() => setDays(r.days)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-all",
                  days === r.days
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {t(r.labelKey)}
              </button>
            ))}
          </div>

          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw
              className={cn("h-4 w-4", loading && "animate-spin")}
            />
            {t("dashboard.refresh")}
          </Button>
        </div>
      </div>

      {userId && (
        <Badge variant="default" className="gap-1">
          <Users className="h-3 w-3" />
          {userId}
          <button
            type="button"
            className="ml-1 text-primary/70 hover:text-primary"
            onClick={() => {
              setUserId("");
              setUserInput("");
            }}
          >
            ✕
          </button>
        </Badge>
      )}

      {loading && (
        <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          {t("dashboard.loading")}
        </div>
      )}

      {!loading && error && (
        <Card>
          <CardContent className="flex items-center gap-3 p-6 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            {error}
          </CardContent>
        </Card>
      )}

      {!loading && !error && !hasData && (
        <Card>
          <CardContent className="py-16 text-center text-muted-foreground">
            {t("dashboard.empty")}
          </CardContent>
        </Card>
      )}

      {!loading && !error && hasData && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <KpiCard
              icon={Activity}
              label={t("dashboard.kpi.tasks")}
              value={stats.total_tasks}
              accent="bg-primary/15 text-primary"
            />
            <KpiCard
              icon={BarChart3}
              label={t("dashboard.kpi.detections")}
              value={stats.total_detections}
              accent="bg-muted text-muted-foreground"
            />
            <KpiCard
              icon={ShieldAlert}
              label={t("dashboard.kpi.flagged")}
              value={stats.total_flagged}
              accent="bg-destructive/15 text-destructive"
            />
            <KpiCard
              icon={AlertTriangle}
              label={t("dashboard.kpi.flaggedRate")}
              value={`${Math.round((stats.flagged_rate || 0) * 100)}%`}
              accent="bg-success/15 text-success"
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{t("dashboard.timeseries.title")}</CardTitle>
              <CardDescription>
                {t("dashboard.timeseries.desc")}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart
                  data={stats.timeseries}
                  margin={{ top: 5, right: 10, left: -10, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="gDet" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor={COLOR_PRIMARY}
                        stopOpacity={0.4}
                      />
                      <stop
                        offset="95%"
                        stopColor={COLOR_PRIMARY}
                        stopOpacity={0}
                      />
                    </linearGradient>
                    <linearGradient id="gFlag" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor={COLOR_FLAGGED}
                        stopOpacity={0.4}
                      />
                      <stop
                        offset="95%"
                        stopColor={COLOR_FLAGGED}
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="hsl(215 14% 60% / 0.15)"
                  />
                  <XAxis
                    dataKey="date"
                    tickFormatter={shortDay}
                    tick={{ fontSize: 12 }}
                    minTickGap={24}
                  />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(222 47% 11%)",
                      border: "1px solid hsl(215 14% 60% / 0.2)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area
                    type="monotone"
                    dataKey="detections"
                    name={t("dashboard.timeseries.detections")}
                    stroke={COLOR_PRIMARY}
                    fill="url(#gDet)"
                    strokeWidth={2}
                  />
                  <Area
                    type="monotone"
                    dataKey="flagged"
                    name={t("dashboard.timeseries.flagged")}
                    stroke={COLOR_FLAGGED}
                    fill="url(#gFlag)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>{t("dashboard.byType.title")}</CardTitle>
                <CardDescription>{t("dashboard.byType.desc")}</CardDescription>
              </CardHeader>
              <CardContent>
                {typeData.length === 0 ? (
                  <p className="py-10 text-center text-sm text-muted-foreground">
                    {t("dashboard.empty")}
                  </p>
                ) : (
                  <ResponsiveContainer width="100%" height={Math.max(220, typeData.length * 40)}>
                    <BarChart
                      data={typeData}
                      layout="vertical"
                      margin={{ top: 0, right: 16, left: 10, bottom: 0 }}
                    >
                      <CartesianGrid
                        horizontal={false}
                        strokeDasharray="3 3"
                        stroke="hsl(215 14% 60% / 0.15)"
                      />
                      <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
                      <YAxis
                        type="category"
                        dataKey="label"
                        width={150}
                        tick={{ fontSize: 12 }}
                      />
                      <Tooltip
                        cursor={{ fill: "hsl(215 14% 60% / 0.08)" }}
                        contentStyle={{
                          background: "hsl(222 47% 11%)",
                          border: "1px solid hsl(215 14% 60% / 0.2)",
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                      />
                      <Bar
                        dataKey="flagged"
                        name={t("dashboard.kpi.flagged")}
                        fill={COLOR_FLAGGED}
                        radius={[0, 4, 4, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t("dashboard.bySeverity.title")}</CardTitle>
                <CardDescription>
                  {t("dashboard.bySeverity.desc")}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {(stats.by_severity ?? []).length === 0 ? (
                  <p className="py-10 text-center text-sm text-muted-foreground">
                    {t("dashboard.empty")}
                  </p>
                ) : (
                  <div className="space-y-4 py-2">
                    {stats.by_severity.map((s) => {
                      const max = Math.max(
                        ...stats.by_severity.map((x) => x.count),
                        1
                      );
                      return (
                        <div key={s.severity} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-medium">
                              {t(`severity.${s.severity}`)}
                            </span>
                            <span className="text-muted-foreground">
                              {s.count}
                            </span>
                          </div>
                          <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${(s.count / max) * 100}%`,
                                background:
                                  SEVERITY_COLORS[s.severity] || COLOR_PRIMARY,
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {!userId && (stats.by_user ?? []).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t("dashboard.byUser.title")}</CardTitle>
                <CardDescription>{t("dashboard.byUser.desc")}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="py-2 pr-4 font-medium">
                          {t("dashboard.byUser.user")}
                        </th>
                        <th className="py-2 pr-4 font-medium">
                          {t("dashboard.byUser.tasks")}
                        </th>
                        <th className="py-2 pr-4 font-medium">
                          {t("dashboard.byUser.flagged")}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.by_user.map((u) => (
                        <tr
                          key={u.user_id}
                          className="border-b border-border/50 last:border-0"
                        >
                          <td className="py-2 pr-4">
                            <button
                              type="button"
                              className="font-medium text-primary hover:underline"
                              onClick={() => {
                                setUserId(u.user_id);
                                setUserInput(u.user_id);
                              }}
                            >
                              {u.user_id}
                            </button>
                          </td>
                          <td className="py-2 pr-4">{u.tasks}</td>
                          <td className="py-2 pr-4">
                            <Badge
                              variant={
                                u.flagged > 0 ? "destructive" : "muted"
                              }
                            >
                              {u.flagged}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-destructive" />
                {t("dashboard.alerts.title")}
              </CardTitle>
              <CardDescription>{t("dashboard.alerts.desc")}</CardDescription>
            </CardHeader>
            <CardContent>
              {(stats.alerts ?? []).length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  {t("dashboard.alerts.empty")}
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="py-2 pr-4 font-medium">
                          {t("dashboard.alerts.type")}
                        </th>
                        <th className="py-2 pr-4 font-medium">
                          {t("dashboard.alerts.severity")}
                        </th>
                        <th className="py-2 pr-4 font-medium">
                          {t("dashboard.alerts.confidence")}
                        </th>
                        <th className="py-2 pr-4 font-medium">
                          {t("dashboard.alerts.user")}
                        </th>
                        <th className="py-2 pr-4 font-medium">
                          {t("dashboard.alerts.when")}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.alerts.map((a, i) => (
                        <tr
                          key={`${a.task_id}-${i}`}
                          className="border-b border-border/50 last:border-0"
                        >
                          <td className="py-2 pr-4 font-medium">
                            {t(`detection.${a.type}`) || a.type}
                          </td>
                          <td className="py-2 pr-4">
                            <Badge variant={severityVariant(a.severity)}>
                              {t(`severity.${a.severity}`) || a.severity}
                            </Badge>
                          </td>
                          <td className="py-2 pr-4">
                            {Math.round((a.confidence || 0) * 100)}%
                          </td>
                          <td className="py-2 pr-4 text-muted-foreground">
                            {a.user_id}
                          </td>
                          <td className="py-2 pr-4 text-muted-foreground">
                            {new Date(a.created_at).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
