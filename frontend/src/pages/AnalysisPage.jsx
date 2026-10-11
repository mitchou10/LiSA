import { useEffect, useMemo, useState } from "react";
import { textToPages } from "../lib/runModel";
import { Link, useSearchParams } from "react-router-dom";
import { FileText, FileUp, Loader2, Play } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import RunDocument from "../components/analysis/RunDocument";
import RunResults from "../components/analysis/RunResults";
import { useProjectRun } from "../hooks/useProjectRun";
import { DEFINITION_KINDS, getDefinitions, getProjects, uploadFile } from "../lib/api";
import { nameField } from "../components/projects/DefinitionDialog";
import { useI18n } from "../lib/i18n.jsx";

// What the run body calls the selection of each kind.
const BODY_FIELD = {
  entities: "entity_ids",
  relations: "relation_ids",
  classifications: "classification_ids",
  safety: "safety_ids",
};

const selectClass =
  "h-10 w-full rounded-md border border-input bg-background/60 px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** What to apply: the project's definitions of one kind, as checkboxes. */
function Selection({ kind, items, selected, onChange, projectId, t }) {
  const toggle = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(next);
  };
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 text-sm font-medium">
        {t(`projects.kind.${kind}`)}
        <span className="text-xs text-muted-foreground">
          {selected.size}/{items.length}
        </span>
        {items.length > 0 && (
          <span className="ml-auto flex gap-2 text-xs">
            <button
              type="button"
              className="text-primary hover:underline"
              onClick={() => onChange(new Set(items.map((d) => d.id)))}
            >
              {t("run.all")}
            </button>
            <button
              type="button"
              className="text-primary hover:underline"
              onClick={() => onChange(new Set())}
            >
              {t("run.none")}
            </button>
          </span>
        )}
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          {t("run.noneDefined")}{" "}
          <Link to={`/projects/${projectId}`} className="text-primary hover:underline">
            {t("run.define")}
          </Link>
        </p>
      ) : (
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {items.map((d) => (
            <label key={d.id} className="flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={selected.has(d.id)}
                onChange={() => toggle(d.id)}
              />
              <span className={d.enabled ? "" : "text-muted-foreground"}>
                {d[nameField(kind)]}
              </span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Analyse a text or files with a project: pick the project, pick what to
 * apply from it, send. The backend feeds the workers in the right order
 * (text -> analysers; file -> parser -> analysers).
 */
export default function AnalysisPage() {
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const { run, running, error, start, reset } = useProjectRun();

  const [projects, setProjects] = useState(null);
  const [projectsError, setProjectsError] = useState(null);
  const projectId = params.get("project") ?? "";
  const [definitions, setDefinitions] = useState(null);
  const [selected, setSelected] = useState({});

  const [source, setSource] = useState("text");
  const [text, setText] = useState("");
  const [files, setFiles] = useState([]);
  const [blur, setBlur] = useState(true);
  // Files: also classify the page images (CLIP) with the same classifications.
  const [classifyImages, setClassifyImages] = useState(true);
  // Hide what was found and keep nothing readable in the database.
  const [anonymize, setAnonymize] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [formError, setFormError] = useState(null);
  // What was sent: a text is cut into pages here, files come back from the parser.
  const [sent, setSent] = useState(null);

  useEffect(() => {
    getProjects()
      .then((list) => {
        setProjects(list);
        // Open on the first project when none is chosen.
        if (list.length && !list.some((p) => p.id === params.get("project"))) {
          setParams({ project: list[0].id }, { replace: true });
        }
      })
      .catch((err) => setProjectsError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The project's definitions; everything enabled is applied by default.
  useEffect(() => {
    if (!projectId) return undefined;
    let active = true;
    setDefinitions(null);
    reset();
    Promise.all(DEFINITION_KINDS.map((k) => getDefinitions(projectId, k)))
      .then((lists) => {
        if (!active) return;
        const defs = Object.fromEntries(DEFINITION_KINDS.map((k, i) => [k, lists[i]]));
        setDefinitions(defs);
        setSelected(
          Object.fromEntries(
            DEFINITION_KINDS.map((k) => [
              k,
              new Set(defs[k].filter((d) => d.enabled).map((d) => d.id)),
            ])
          )
        );
      })
      .catch((err) => active && setProjectsError(err.message));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const selectedCount = useMemo(
    () => DEFINITION_KINDS.reduce((n, k) => n + (selected[k]?.size ?? 0), 0),
    [selected]
  );
  const hasInput = source === "text" ? text.trim().length > 0 : files.length > 0;
  const busy = running || uploading;
  const canRun = projectId && definitions && selectedCount > 0 && hasInput && !busy;

  const onRun = async () => {
    setFormError(null);
    try {
      const body = Object.fromEntries(
        DEFINITION_KINDS.map((k) => [BODY_FIELD[k], [...selected[k]]])
      );
      body.anonymize = anonymize;
      if (source === "text") {
        body.text = text;
        setSent({ kind: "text", pages: textToPages(text) });
      } else {
        setSent({ kind: "files" });
        setUploading(true);
        const uploaded = [];
        for (const file of files) uploaded.push(await uploadFile(file));
        body.file_ids = uploaded.map((f) => f.id);
        body.blur_screenshots = blur;
        body.classify_images = classifyImages;
        setUploading(false);
      }
      await start(projectId, body);
    } catch (err) {
      setUploading(false);
      setFormError(err.message);
    }
  };

  if (projectsError && !projects)
    return <p className="text-sm text-destructive">{projectsError}</p>;
  if (!projects) return <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />;
  if (projects.length === 0)
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("run.noProject.title")}</CardTitle>
          <CardDescription>{t("run.noProject.desc")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/projects">
            <Button>{t("run.noProject.cta")}</Button>
          </Link>
        </CardContent>
      </Card>
    );

  return (
    <div className="space-y-6">
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>{t("run.title")}</CardTitle>
          <CardDescription>{t("run.desc")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="project">
              {t("run.project")}
            </label>
            <div className="flex items-center gap-2">
              <select
                id="project"
                className={selectClass}
                value={projectId}
                onChange={(e) => setParams({ project: e.target.value })}
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <Link
                to={`/projects/${projectId}`}
                className="shrink-0 text-sm text-primary hover:underline"
              >
                {t("run.manage")}
              </Link>
            </div>
          </div>

          {!definitions ? (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          ) : (
            <div className="space-y-4 rounded-lg border border-border p-3">
              <div className="text-sm font-medium">{t("run.apply")}</div>
              {DEFINITION_KINDS.map((kind) => (
                <Selection
                  key={kind}
                  kind={kind}
                  items={definitions[kind]}
                  selected={selected[kind] ?? new Set()}
                  onChange={(next) => setSelected({ ...selected, [kind]: next })}
                  projectId={projectId}
                  t={t}
                />
              ))}
            </div>
          )}

          <Tabs value={source} onValueChange={setSource}>
            <TabsList className="w-full">
              <TabsTrigger value="text" className="flex-1">
                <FileText className="h-4 w-4" /> {t("analyze.tab.text")}
              </TabsTrigger>
              <TabsTrigger value="file" className="flex-1">
                <FileUp className="h-4 w-4" /> {t("analyze.tab.file")}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="text">
              <Textarea
                rows={8}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={t("run.text.placeholder")}
              />
            </TabsContent>
            <TabsContent value="file" className="space-y-3">
              <input
                type="file"
                multiple
                accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp"
                onChange={(e) => setFiles([...e.target.files])}
                className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-2 file:text-sm file:font-medium"
              />
              {files.length > 0 && (
                <ul className="text-xs text-muted-foreground">
                  {files.map((f) => (
                    <li key={f.name + f.size}>
                      {f.name} · {(f.size / 1024).toFixed(0)} KB
                    </li>
                  ))}
                </ul>
              )}
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={blur}
                  onChange={(e) => setBlur(e.target.checked)}
                />
                {t("run.blur")}
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={classifyImages}
                  onChange={(e) => setClassifyImages(e.target.checked)}
                />
                {t("run.classifyImages")}
              </label>
              <p className="text-xs text-muted-foreground">{t("run.classifyImages.hint")}</p>
              <p className="text-xs text-muted-foreground">{t("run.file.hint")}</p>
            </TabsContent>
          </Tabs>

          <Button className="w-full" disabled={!canRun} onClick={onRun}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {uploading ? t("run.uploading") : running ? t("run.running") : t("run.start")}
          </Button>
          {(formError || error) && (
            <p className="text-sm text-destructive">{formError || error}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("analyze.results.title")}</CardTitle>
          <CardDescription>{t("run.results.desc")}</CardDescription>
        </CardHeader>
        <CardContent>
          {run ? (
            <RunResults run={run} />
          ) : (
            <p className="text-sm text-muted-foreground">{t("run.results.empty")}</p>
          )}
        </CardContent>
      </Card>
    </div>
    {run && <RunDocument run={run} source={sent} />}
    </div>
  );
}
