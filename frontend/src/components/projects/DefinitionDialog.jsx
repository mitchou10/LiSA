import { useEffect, useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { Dialog } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Textarea } from "../ui/textarea";
import { useI18n } from "../../lib/i18n.jsx";

const SEVERITIES = ["low", "medium", "high"];
const ACTIONS = ["allow", "redact", "block"];

const selectClass =
  "h-10 w-full rounded-md border border-input bg-background/60 px-2 text-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring";

// The field that names a definition: entities have a label, the rest a name.
export const nameField = (kind) => (kind === "entities" ? "label" : "name");

const hasLabels = (kind) => kind === "classifications" || kind === "safety";

function blank(kind) {
  const base = { description: "", threshold: "", enabled: true };
  if (kind === "entities")
    return { ...base, label: "", category: "OTHER", severity: "medium", action: "redact" };
  if (kind === "relations") return { ...base, name: "" };
  return {
    ...base,
    name: "",
    multi_label: false,
    labels:
      kind === "safety"
        ? [
            { name: "", description: "", is_ok: true },
            { name: "", description: "", is_ok: false },
          ]
        : [
            { name: "", description: "" },
            { name: "", description: "" },
          ],
  };
}

function fromDefinition(kind, d) {
  const form = { ...blank(kind), ...d, description: d.description ?? "" };
  form.threshold = d.threshold ?? "";
  if (hasLabels(kind)) {
    form.labels = d.labels.map((l) => ({
      name: l.name,
      description: l.description ?? "",
      is_ok: l.is_ok ?? false,
    }));
  }
  return form;
}

// Form -> API payload: trimmed text, empty -> null, no blank label.
function toPayload(kind, form) {
  const payload = {
    [nameField(kind)]: form[nameField(kind)].trim(),
    description: form.description.trim() || null,
    threshold: form.threshold === "" ? null : Number(form.threshold),
    enabled: form.enabled,
  };
  if (kind === "entities") {
    payload.category = form.category.trim().toUpperCase() || "OTHER";
    payload.severity = form.severity;
    payload.action = form.action;
  }
  if (hasLabels(kind)) {
    payload.multi_label = form.multi_label;
    payload.labels = form.labels
      .filter((l) => l.name.trim())
      .map((l) => ({
        name: l.name.trim(),
        description: l.description.trim() || null,
        ...(kind === "safety" ? { is_ok: l.is_ok } : {}),
      }));
  }
  return payload;
}

function Field({ label, hint, children }) {
  return (
    <label className="block space-y-1">
      <span className="block text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}

/** Create or edit one definition (entity, relation, classification, safety). */
export default function DefinitionDialog({ open, kind, definition, onClose, onSave }) {
  const { t } = useI18n();
  const [form, setForm] = useState(() => blank(kind));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) return;
    setForm(definition ? fromDefinition(kind, definition) : blank(kind));
    setError(null);
  }, [open, kind, definition]);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const setLabel = (i, patch) =>
    set({ labels: form.labels.map((l, j) => (j === i ? { ...l, ...patch } : l)) });

  const validate = () => {
    if (!form[nameField(kind)].trim()) return t("projects.error.name");
    if (form.threshold !== "" && (form.threshold < 0 || form.threshold > 1))
      return t("projects.error.threshold");
    if (hasLabels(kind)) {
      const labels = form.labels.filter((l) => l.name.trim());
      if (labels.length === 0) return t("projects.error.labels");
      const names = labels.map((l) => l.name.trim().toLowerCase());
      if (new Set(names).size !== names.length) return t("projects.error.duplicate");
      if (kind === "safety" && !labels.some((l) => l.is_ok))
        return t("projects.error.ok");
    }
    return null;
  };

  const submit = async (e) => {
    e.preventDefault();
    const problem = validate();
    if (problem) return setError(problem);
    setSaving(true);
    setError(null);
    try {
      await onSave(toPayload(kind, form));
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const title = `${definition ? t("projects.edit") : t("projects.add")} · ${t(`projects.kind.${kind}.one`)}`;

  return (
    <Dialog open={open} onClose={onClose} title={title} className="max-w-xl">
      <form className="space-y-4" onSubmit={submit}>
        <Field label={t(`projects.field.${nameField(kind)}`)}>
          <Input
            autoFocus
            value={form[nameField(kind)]}
            onChange={(e) => set({ [nameField(kind)]: e.target.value })}
          />
        </Field>

        <Field
          label={t("projects.field.description")}
          hint={t(`projects.hint.description.${kind}`)}
        >
          <Textarea
            rows={2}
            value={form.description}
            onChange={(e) => set({ description: e.target.value })}
          />
        </Field>

        {kind === "entities" && (
          <div className="grid grid-cols-3 gap-3">
            <Field label={t("projects.field.category")}>
              <Input
                className="uppercase"
                value={form.category}
                onChange={(e) => set({ category: e.target.value.toUpperCase() })}
              />
            </Field>
            <Field label={t("projects.field.severity")}>
              <select
                className={selectClass}
                value={form.severity}
                onChange={(e) => set({ severity: e.target.value })}
              >
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>
                    {t(`sensitive.severity.${s}`)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("projects.field.action")}>
              <select
                className={selectClass}
                value={form.action}
                onChange={(e) => set({ action: e.target.value })}
              >
                {ACTIONS.map((a) => (
                  <option key={a} value={a}>
                    {t(`sensitive.action.${a}`)}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        )}

        {hasLabels(kind) && (
          <>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.multi_label}
                onChange={(e) => set({ multi_label: e.target.checked })}
              />
              <span className="font-medium">{t("projects.field.multi")}</span>
              <span className="text-xs text-muted-foreground">
                {form.multi_label ? t("projects.hint.multi") : t("projects.hint.single")}
              </span>
            </label>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{t("projects.field.labels")}</span>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    set({
                      labels: [...form.labels, { name: "", description: "", is_ok: false }],
                    })
                  }
                >
                  <Plus className="h-4 w-4" />
                  {t("projects.addLabel")}
                </Button>
              </div>
              {kind === "safety" && (
                <p className="text-xs text-muted-foreground">{t("projects.hint.ok")}</p>
              )}
              {form.labels.map((label, i) => (
                <div key={i} className="flex items-start gap-2">
                  <Input
                    className="w-40 shrink-0"
                    placeholder={t("projects.field.labelName")}
                    value={label.name}
                    onChange={(e) => setLabel(i, { name: e.target.value })}
                  />
                  <Input
                    placeholder={t("projects.field.labelDescription")}
                    value={label.description}
                    onChange={(e) => setLabel(i, { description: e.target.value })}
                  />
                  {kind === "safety" && (
                    <label
                      className="flex h-10 shrink-0 items-center gap-1 text-xs"
                      title={t("projects.hint.ok")}
                    >
                      <input
                        type="checkbox"
                        checked={label.is_ok}
                        onChange={(e) => setLabel(i, { is_ok: e.target.checked })}
                      />
                      OK
                    </label>
                  )}
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    aria-label={t("projects.removeLabel")}
                    onClick={() =>
                      set({ labels: form.labels.filter((_, j) => j !== i) })
                    }
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          </>
        )}

        <div className="flex flex-wrap items-end gap-6">
          <Field
            label={t("projects.field.threshold")}
            hint={t("projects.hint.threshold")}
          >
            <Input
              type="number"
              min="0"
              max="1"
              step="0.05"
              className="w-28"
              placeholder="—"
              value={form.threshold}
              onChange={(e) => set({ threshold: e.target.value })}
            />
          </Field>
          <label className="flex h-10 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => set({ enabled: e.target.checked })}
            />
            {t("projects.field.enabled")}
          </label>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            {t("projects.cancel")}
          </Button>
          <Button type="submit" disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {t("projects.save")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
