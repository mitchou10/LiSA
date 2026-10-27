import { useState } from "react";
import { Link } from "react-router-dom";
import { FolderKanban, Loader2, Plus, Sparkles, Wand2, X } from "lucide-react";
import { Button } from "../../ui/button";
import { Input } from "../../ui/input";
import { DEFINITION_KINDS } from "../../../lib/api";
import { nameField } from "../../projects/DefinitionDialog";
import { cn } from "../../../lib/utils";
import { useI18n } from "../../../lib/i18n.jsx";
import OptionCard from "./OptionCard";

// Labels offered when creating a project on the fly.
export const PRESET_LABELS = [
  "PERSON",
  "EMAIL_ADDRESS",
  "PHONE_NUMBER",
  "IBAN",
  "DATE_OF_BIRTH",
  "ADDRESS",
  "CREDIT_CARD",
  "ORGANIZATION",
];

const selectClass =
  "h-10 w-full rounded-md border border-input bg-background/60 px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

function Check({ checked, onChange, children }) {
  return (
    <label className="flex items-start gap-2 text-sm">
      <input type="checkbox" className="mt-0.5" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{children}</span>
    </label>
  );
}

/** What of a project to apply: its definitions of each kind, as chips. */
function Definitions({ definitions, selected, onChange, projectId, t }) {
  if (!definitions) return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />;
  const toggle = (kind, id) => {
    const next = new Set(selected[kind]);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange({ ...selected, [kind]: next });
  };
  const kinds = DEFINITION_KINDS.filter((k) => definitions[k].length > 0);
  if (kinds.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        {t("run.noneDefined")}{" "}
        <Link to={`/projects/${projectId}`} className="text-primary hover:underline">
          {t("run.define")}
        </Link>
      </p>
    );
  return (
    <div className="space-y-3">
      <div className="text-sm font-medium">{t("run.apply")}</div>
      {kinds.map((kind) => (
        <div key={kind} className="space-y-1.5">
          <div className="text-xs text-muted-foreground">{t(`projects.kind.${kind}`)}</div>
          <div className="flex flex-wrap gap-1.5">
            {definitions[kind].map((d) => (
              <button
                type="button"
                key={d.id}
                onClick={() => toggle(kind, d.id)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                  selected[kind]?.has(d.id)
                    ? "border-primary bg-primary/15 text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground"
                )}
              >
                {d[nameField(kind)]}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Quick project: a name and the labels to look for. */
function NewProject({ value, onChange, t }) {
  const [custom, setCustom] = useState("");
  const toggle = (label) => {
    const labels = new Set(value.labels);
    if (labels.has(label)) labels.delete(label);
    else labels.add(label);
    onChange({ ...value, labels });
  };
  const addCustom = () => {
    const label = custom.trim().toUpperCase().replace(/\s+/g, "_");
    if (!label) return;
    onChange({ ...value, labels: new Set([...value.labels, label]) });
    setCustom("");
  };
  const all = [...new Set([...PRESET_LABELS, ...value.labels])];
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <label className="text-sm font-medium" htmlFor="new-project-name">
          {t("wiz.new.name")}
        </label>
        <Input
          id="new-project-name"
          value={value.name}
          onChange={(e) => onChange({ ...value, name: e.target.value })}
          placeholder={t("wiz.new.name.placeholder")}
        />
      </div>
      <div className="space-y-1.5">
        <div className="text-sm font-medium">{t("wiz.new.labels")}</div>
        <div className="flex flex-wrap gap-1.5">
          {all.map((label) => (
            <button
              type="button"
              key={label}
              onClick={() => toggle(label)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                value.labels.has(label)
                  ? "border-primary bg-primary/15 text-foreground"
                  : "border-border text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
              {!PRESET_LABELS.includes(label) && <X className="ml-1 inline h-3 w-3" />}
            </button>
          ))}
        </div>
        <div className="flex gap-2 pt-1">
          <Input
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustom())}
            placeholder={t("wiz.new.custom")}
          />
          <Button type="button" variant="outline" onClick={addCustom} disabled={!custom.trim()}>
            <Plus className="h-4 w-4" />
            {t("wiz.new.add")}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">{t("wiz.new.hint")}</p>
      </div>
    </div>
  );
}

/** Step 2: which analysis to apply, plus the few options that go with it. */
export default function StepAnalysis({
  mode,
  onMode,
  projects,
  projectId,
  onProject,
  definitions,
  selected,
  onSelected,
  newProject,
  onNewProject,
  isFile,
  options,
  onOptions,
}) {
  const { t } = useI18n();
  return (
    <div className="space-y-4" role="radiogroup" aria-label={t("wiz.analysis.title")}>
      <OptionCard
        icon={Sparkles}
        title={t("wiz.mode.default")}
        desc={t("wiz.mode.default.desc")}
        badge={t("wiz.recommended")}
        selected={mode === "default"}
        onSelect={() => onMode("default")}
      >
        <p className="text-sm text-muted-foreground">{t("run.default.applies")}</p>
      </OptionCard>

      <OptionCard
        icon={FolderKanban}
        title={t("wiz.mode.project")}
        desc={t("wiz.mode.project.desc")}
        selected={mode === "project"}
        onSelect={() => onMode("project")}
      >
        {projects.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("wiz.project.none")}</p>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <select
                aria-label={t("run.project")}
                className={selectClass}
                value={projectId}
                onChange={(e) => onProject(e.target.value)}
              >
                <option value="">{t("wiz.project.pick")}</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              {projectId && (
                <Link to={`/projects/${projectId}`} className="shrink-0 text-sm text-primary hover:underline">
                  {t("run.manage")}
                </Link>
              )}
            </div>
            {projectId && (
              <Definitions
                definitions={definitions}
                selected={selected}
                onChange={onSelected}
                projectId={projectId}
                t={t}
              />
            )}
          </div>
        )}
      </OptionCard>

      <OptionCard
        icon={Wand2}
        title={t("wiz.mode.new")}
        desc={t("wiz.mode.new.desc")}
        selected={mode === "new"}
        onSelect={() => onMode("new")}
      >
        <NewProject value={newProject} onChange={onNewProject} t={t} />
      </OptionCard>

      <div className="space-y-2 rounded-xl border border-border p-4">
        <div className="text-sm font-medium">{t("wiz.options.title")}</div>
        <Check checked={options.anonymize} onChange={(v) => onOptions({ ...options, anonymize: v })}>
          {t("wiz.options.anonymize")}
        </Check>
        {isFile && (
          <>
            <Check checked={options.blur} onChange={(v) => onOptions({ ...options, blur: v })}>
              {t("run.blur")}
            </Check>
            <Check
              checked={options.classifyImages}
              onChange={(v) => onOptions({ ...options, classifyImages: v })}
            >
              {t("run.classifyImages")}
            </Check>
          </>
        )}
      </div>
    </div>
  );
}
