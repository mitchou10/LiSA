import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Plus, RotateCcw, Save, Trash2, Undo2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { cn } from "../lib/utils";
import {
  getDetectionProfile,
  getProfileVersions,
  saveProfileVersion,
  restoreProfileVersion,
} from "../lib/api";
import { useAuth } from "../lib/auth.jsx";
import { useI18n } from "../lib/i18n.jsx";

const SERVICE_KEY = "gliner-ner";
const SEVERITIES = ["low", "medium", "high"];
const ACTIONS = ["allow", "redact", "block"];

const selectClass =
  "h-9 rounded-md border border-input bg-background/60 px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60";

// Stable comparison of a config (ignores nothing: any field change counts).
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// Entity-level diff between two configs, keyed by (case-insensitive) label.
function diffConfigs(from, to) {
  const key = (e) => e.label.toLowerCase();
  const a = new Map(from.entities.map((e) => [key(e), e]));
  const b = new Map(to.entities.map((e) => [key(e), e]));
  const rows = [];
  for (const [k, e] of b) {
    if (!a.has(k)) rows.push({ kind: "added", label: e.label });
    else if (!same(a.get(k), e)) rows.push({ kind: "changed", label: e.label });
  }
  for (const [k, e] of a) if (!b.has(k)) rows.push({ kind: "removed", label: e.label });
  if (from.threshold !== to.threshold)
    rows.push({ kind: "changed", label: `threshold ${from.threshold} → ${to.threshold}` });
  return rows;
}

const DIFF_STYLE = {
  added: "text-success",
  removed: "text-destructive",
  changed: "text-primary",
};

export default function SensitiveDataPage() {
  const { t } = useI18n();
  const { isAdmin } = useAuth();

  const [profile, setProfile] = useState(null);
  const [versions, setVersions] = useState([]);
  const [draft, setDraft] = useState(null);
  const [filter, setFilter] = useState("");
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [compare, setCompare] = useState(null);

  const load = useCallback(async () => {
    try {
      const [p, v] = await Promise.all([
        getDetectionProfile(SERVICE_KEY),
        getProfileVersions(SERVICE_KEY),
      ]);
      setProfile(p);
      setVersions(v);
      setDraft(structuredClone(p.active.config));
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const active = profile?.active;
  const dirty = draft && active && !same(draft, active.config);

  const validation = useMemo(() => {
    if (!draft) return null;
    if (draft.entities.some((e) => !e.label.trim() || !e.category.trim()))
      return t("sensitive.error.empty");
    const seen = new Set();
    for (const e of draft.entities) {
      const k = e.label.trim().toLowerCase();
      if (seen.has(k)) return t("sensitive.error.duplicate").replace("{label}", e.label);
      seen.add(k);
    }
    return null;
  }, [draft, t]);

  const rows = useMemo(() => {
    if (!draft) return [];
    const q = filter.trim().toLowerCase();
    return draft.entities
      .map((entity, index) => ({ entity, index }))
      .filter(
        ({ entity }) =>
          !q ||
          entity.label.toLowerCase().includes(q) ||
          entity.category.toLowerCase().includes(q)
      );
  }, [draft, filter]);

  const updateEntity = (index, patch) =>
    setDraft((d) => ({
      ...d,
      entities: d.entities.map((e, i) => (i === index ? { ...e, ...patch } : e)),
    }));

  const addEntity = () =>
    setDraft((d) => ({
      ...d,
      entities: [
        ...d.entities,
        {
          label: "",
          category: "PII",
          severity: "medium",
          action: "redact",
          enabled: true,
          threshold: null,
        },
      ],
    }));

  const removeEntity = (index) =>
    setDraft((d) => ({ ...d, entities: d.entities.filter((_, i) => i !== index) }));

  const run = async (fn, messageKey) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await fn();
      setComment("");
      setCompare(null);
      await load();
      setNotice(t(messageKey).replace("{v}", created.version));
    } catch (e) {
      setError(
        Array.isArray(e.message) ? JSON.stringify(e.message) : String(e.message)
      );
    } finally {
      setBusy(false);
    }
  };

  const save = () =>
    run(
      () =>
        saveProfileVersion(SERVICE_KEY, {
          config: {
            ...draft,
            entities: draft.entities.map((e) => ({ ...e, label: e.label.trim() })),
          },
          comment,
        }),
      "sensitive.saved"
    );

  const restore = (v) =>
    run(() => restoreProfileVersion(SERVICE_KEY, v.version), "sensitive.restored");

  if (loading) {
    return (
      <div className="flex justify-center py-20 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  if (!profile) {
    return (
      <p className="rounded-md bg-destructive/10 p-4 text-sm text-destructive">{error}</p>
    );
  }

  const compareRows = compare && diffConfigs(active.config, compare.config);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-3">
              <CardTitle>{t("sensitive.title")}</CardTitle>
              <Badge>
                {t("sensitive.version")} {active.version} · {t("sensitive.active")}
              </Badge>
              {dirty && <Badge variant="destructive">{t("sensitive.unsaved")}</Badge>}
            </div>
            <CardDescription>{t("sensitive.desc")}</CardDescription>
            {!isAdmin && (
              <p className="text-sm text-muted-foreground">{t("sensitive.readonly")}</p>
            )}
          </CardHeader>
          <CardContent className="space-y-3">
            <label className="block text-sm font-medium">{t("sensitive.threshold")}</label>
            <div className="flex flex-wrap items-center gap-3">
              <Input
                type="number"
                min="0"
                max="1"
                step="0.05"
                className="w-28"
                disabled={!isAdmin}
                value={draft.threshold}
                onChange={(e) =>
                  setDraft({ ...draft, threshold: Number(e.target.value) })
                }
              />
              <span className="text-xs text-muted-foreground">
                {t("sensitive.threshold.hint")}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-3">
              <CardTitle>
                {t("sensitive.entities")} ({draft.entities.length})
              </CardTitle>
              <Input
                className="ml-auto w-64"
                placeholder={t("sensitive.filter")}
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
              {isAdmin && (
                <Button size="sm" variant="outline" onClick={addEntity}>
                  <Plus className="h-4 w-4" />
                  {t("sensitive.add")}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="pb-2 pr-2">{t("sensitive.col.enabled")}</th>
                  <th className="pb-2 pr-2">{t("sensitive.col.label")}</th>
                  <th className="pb-2 pr-2">{t("sensitive.col.category")}</th>
                  <th className="pb-2 pr-2">{t("sensitive.col.severity")}</th>
                  <th className="pb-2 pr-2">{t("sensitive.col.action")}</th>
                  <th className="pb-2 pr-2">{t("sensitive.col.threshold")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map(({ entity, index }) => (
                  <tr key={index} className="border-t border-border">
                    <td className="py-1.5 pr-2">
                      <input
                        type="checkbox"
                        checked={entity.enabled}
                        disabled={!isAdmin}
                        onChange={(e) => updateEntity(index, { enabled: e.target.checked })}
                      />
                    </td>
                    <td className="py-1.5 pr-2">
                      <Input
                        className="h-9 min-w-40"
                        placeholder={t("sensitive.newLabel")}
                        disabled={!isAdmin}
                        value={entity.label}
                        onChange={(e) => updateEntity(index, { label: e.target.value })}
                      />
                    </td>
                    <td className="py-1.5 pr-2">
                      <Input
                        className="h-9 w-28 uppercase"
                        disabled={!isAdmin}
                        value={entity.category}
                        onChange={(e) =>
                          updateEntity(index, { category: e.target.value.toUpperCase() })
                        }
                      />
                    </td>
                    <td className="py-1.5 pr-2">
                      <select
                        className={selectClass}
                        disabled={!isAdmin}
                        value={entity.severity}
                        onChange={(e) => updateEntity(index, { severity: e.target.value })}
                      >
                        {SEVERITIES.map((s) => (
                          <option key={s} value={s}>
                            {t(`sensitive.severity.${s}`)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-1.5 pr-2">
                      <select
                        className={selectClass}
                        disabled={!isAdmin}
                        value={entity.action}
                        onChange={(e) => updateEntity(index, { action: e.target.value })}
                      >
                        {ACTIONS.map((a) => (
                          <option key={a} value={a}>
                            {t(`sensitive.action.${a}`)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-1.5 pr-2">
                      <Input
                        type="number"
                        min="0"
                        max="1"
                        step="0.05"
                        className="h-9 w-24"
                        placeholder={String(draft.threshold)}
                        disabled={!isAdmin}
                        value={entity.threshold ?? ""}
                        onChange={(e) =>
                          updateEntity(index, {
                            threshold: e.target.value === "" ? null : Number(e.target.value),
                          })
                        }
                      />
                    </td>
                    <td className="py-1.5 text-right">
                      {isAdmin && (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-9 w-9"
                          onClick={() => removeEntity(index)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        {isAdmin && (
          <Card>
            <CardContent className="space-y-3 pt-6">
              <Input
                placeholder={t("sensitive.comment")}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
              {(validation || error) && (
                <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {validation || error}
                </p>
              )}
              {notice && !dirty && (
                <p className="rounded-md bg-success/10 p-3 text-sm text-success">{notice}</p>
              )}
              <div className="flex gap-2">
                <Button onClick={save} disabled={!dirty || !!validation || busy}>
                  {busy ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  {busy ? t("sensitive.saving") : t("sensitive.save")}
                </Button>
                <Button
                  variant="outline"
                  disabled={!dirty || busy}
                  onClick={() => setDraft(structuredClone(active.config))}
                >
                  <Undo2 className="h-4 w-4" />
                  {t("sensitive.discard")}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      <Card className="h-fit">
        <CardHeader>
          <CardTitle>{t("sensitive.history")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {versions.map((v) => (
            <div
              key={v.id}
              className={cn(
                "rounded-md border border-border p-3 text-sm",
                compare?.version === v.version && "border-primary"
              )}
            >
              <div className="flex items-center gap-2">
                <span className="font-semibold">v{v.version}</span>
                {v.is_active && <Badge variant="success">{t("sensitive.active")}</Badge>}
                <span className="ml-auto text-xs text-muted-foreground">
                  {new Date(v.created_at).toLocaleString()}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{v.created_by}</p>
              {v.comment && <p className="mt-1">{v.comment}</p>}
              {!v.is_active && (
                <div className="mt-2 flex gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setCompare(compare?.version === v.version ? null : v)}
                  >
                    {t("sensitive.diff")}
                  </Button>
                  {isAdmin && (
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => restore(v)}>
                      <RotateCcw className="h-3.5 w-3.5" />
                      {t("sensitive.restore")}
                    </Button>
                  )}
                </div>
              )}
              {compare?.version === v.version && (
                <ul className="mt-2 space-y-0.5 border-t border-border pt-2 text-xs">
                  {compareRows.length === 0 && <li>{t("sensitive.diff.none")}</li>}
                  {compareRows.map((r, i) => (
                    <li key={i} className={DIFF_STYLE[r.kind]}>
                      {t(`sensitive.diff.${r.kind}`)}: {r.label}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
