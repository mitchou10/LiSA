import { useCallback, useEffect, useState } from "react";
import { Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import {
  createDefinition,
  deleteDefinition,
  getDefinitions,
  updateDefinition,
} from "../../lib/api";
import { useI18n } from "../../lib/i18n.jsx";
import DefinitionDialog, { nameField } from "./DefinitionDialog";

const SEVERITY_VARIANT = { low: "muted", medium: "default", high: "destructive" };

function Details({ kind, d, t }) {
  if (kind === "entities")
    return (
      <div className="flex flex-wrap gap-1.5">
        <Badge variant="muted">{d.category}</Badge>
        <Badge variant={SEVERITY_VARIANT[d.severity]}>
          {t(`sensitive.severity.${d.severity}`)}
        </Badge>
        <Badge variant="muted">{t(`sensitive.action.${d.action}`)}</Badge>
      </div>
    );
  if (kind === "relations") return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Badge variant="muted">
        {d.multi_label ? t("projects.multi") : t("projects.single")}
      </Badge>
      {d.labels.map((l) => (
        <Badge
          key={l.id}
          variant={l.is_ok ? "success" : "default"}
          title={l.description || undefined}
        >
          {l.name}
        </Badge>
      ))}
    </div>
  );
}

/** The definitions of one kind in a project: list, add, edit, delete. */
export default function DefinitionsPanel({ projectId, kind, onChange }) {
  const { t } = useI18n();
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(undefined); // undefined: closed, null: new

  const load = useCallback(async () => {
    try {
      setItems(await getDefinitions(projectId, kind));
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [projectId, kind]);

  useEffect(() => {
    setItems(null);
    load();
  }, [load]);

  const changed = async () => {
    await load();
    onChange?.();
  };

  const save = async (payload) => {
    if (editing) await updateDefinition(projectId, kind, editing.id, payload);
    else await createDefinition(projectId, kind, payload);
    setEditing(undefined);
    await changed();
  };

  const toggle = async (d) => {
    try {
      await updateDefinition(projectId, kind, d.id, { enabled: !d.enabled });
      await changed();
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (d) => {
    if (!window.confirm(t("projects.confirm.delete").replace("{name}", d[nameField(kind)])))
      return;
    try {
      await deleteDefinition(projectId, kind, d.id);
      await changed();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-3">
          <CardTitle>
            {t(`projects.kind.${kind}`)} {items && `(${items.length})`}
          </CardTitle>
          <Button size="sm" className="ml-auto" onClick={() => setEditing(null)}>
            <Plus className="h-4 w-4" />
            {t("projects.add")}
          </Button>
        </div>
        <CardDescription>{t(`projects.kind.${kind}.desc`)}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {error && <p className="text-sm text-destructive">{error}</p>}
        {items === null && !error && (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        )}
        {items?.length === 0 && (
          <p className="text-sm text-muted-foreground">{t("projects.empty")}</p>
        )}
        {items?.map((d) => (
          <div
            key={d.id}
            className="flex flex-wrap items-start gap-3 rounded-lg border border-border bg-background/40 p-3"
          >
            <input
              type="checkbox"
              className="mt-1"
              checked={d.enabled}
              onChange={() => toggle(d)}
              title={t("projects.field.enabled")}
            />
            <div className="min-w-0 flex-1 space-y-1">
              <div className="font-medium">{d[nameField(kind)]}</div>
              {d.description && (
                <p className="text-sm text-muted-foreground">{d.description}</p>
              )}
              <Details kind={kind} d={d} t={t} />
            </div>
            {d.threshold != null && (
              <Badge variant="muted">≥ {d.threshold}</Badge>
            )}
            <Button
              size="icon"
              variant="ghost"
              aria-label={t("projects.edit")}
              onClick={() => setEditing(d)}
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              aria-label={t("projects.delete")}
              onClick={() => remove(d)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </CardContent>

      <DefinitionDialog
        open={editing !== undefined}
        kind={kind}
        definition={editing ?? null}
        onClose={() => setEditing(undefined)}
        onSave={save}
      />
    </Card>
  );
}
