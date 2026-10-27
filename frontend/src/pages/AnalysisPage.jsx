import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Loader2, Play, RotateCcw } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import Stepper from "../components/analysis/wizard/Stepper";
import StepSource from "../components/analysis/wizard/StepSource";
import StepAnalysis from "../components/analysis/wizard/StepAnalysis";
import StepRun from "../components/analysis/wizard/StepRun";
import StepResults from "../components/analysis/wizard/StepResults";
import { useProjectRun } from "../hooks/useProjectRun";
import {
  DEFINITION_KINDS,
  createDefinition,
  createProject,
  getDefinitions,
  getProjects,
  uploadFile,
} from "../lib/api";
import { textToPages } from "../lib/runModel";
import { useI18n } from "../lib/i18n.jsx";
import { useUnsavedWork } from "../lib/unsavedWork.jsx";

const SOURCE = 0;
const ANALYSIS = 1;
const RUN = 2;
const RESULTS = 3;
const TERMINAL = ["success", "error", "revoked"];

// What the run body calls the selection of each kind.
const BODY_FIELD = {
  entities: "entity_ids",
  relations: "relation_ids",
  classifications: "classification_ids",
  safety: "safety_ids",
};

// Severity and action of a label created on the fly: what to hide is hidden.
const PRESET_RULES = {
  IBAN: { category: "FINANCIAL", severity: "high", action: "block" },
  CREDIT_CARD: { category: "FINANCIAL", severity: "high", action: "block" },
  DATE_OF_BIRTH: { category: "IDENTITY", severity: "high", action: "redact" },
  PERSON: { category: "IDENTITY", severity: "medium", action: "redact" },
  ORGANIZATION: { category: "BUSINESS", severity: "low", action: "allow" },
};

const entityPayload = (label) => ({
  label,
  description: null,
  threshold: null,
  enabled: true,
  category: "OTHER",
  severity: "medium",
  action: "redact",
  ...(PRESET_RULES[label] ?? {}),
});

/**
 * Analyse a text or files in four steps: what to analyse, how, the progress,
 * then the results where pages can be blurred and exported. The backend feeds
 * the workers in the right order (text -> analysers; file -> parser ->
 * analysers).
 */
export default function AnalysisPage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const { run, running, error, start, reset } = useProjectRun();

  const [step, setStep] = useState(SOURCE);
  const [reached, setReached] = useState(SOURCE);

  // 1. Source
  const [source, setSource] = useState("text");
  const [text, setText] = useState("");
  const [files, setFiles] = useState([]);

  // 2. Analysis
  const [projects, setProjects] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [mode, setMode] = useState(params.get("project") ? "project" : "default");
  const [projectId, setProjectId] = useState(params.get("project") ?? "");
  const [definitions, setDefinitions] = useState(null);
  const [selected, setSelected] = useState({});
  const [newProject, setNewProject] = useState({
    name: "",
    labels: new Set(["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"]),
  });
  const [options, setOptions] = useState({ anonymize: false, blur: true, classifyImages: true });
  const created = useRef(null); // { key, id, entityIds }: the project made on the fly

  // 3. Run
  const [uploading, setUploading] = useState(false);
  const [formError, setFormError] = useState(null);
  // What was sent: a text is cut into pages here, files come back from the parser.
  const [sent, setSent] = useState(null);

  useEffect(() => {
    getProjects()
      .then(setProjects)
      .catch((err) => setLoadError(err.message));
  }, []);

  // The project's definitions; everything enabled is applied by default.
  useEffect(() => {
    if (mode !== "project" || !projectId) {
      setDefinitions(null);
      return undefined;
    }
    let active = true;
    setDefinitions(null);
    Promise.all(DEFINITION_KINDS.map((k) => getDefinitions(projectId, k)))
      .then((lists) => {
        if (!active) return;
        const defs = Object.fromEntries(DEFINITION_KINDS.map((k, i) => [k, lists[i]]));
        setDefinitions(defs);
        setSelected(
          Object.fromEntries(
            DEFINITION_KINDS.map((k) => [k, new Set(defs[k].filter((d) => d.enabled).map((d) => d.id))])
          )
        );
      })
      .catch((err) => active && setLoadError(err.message));
    return () => {
      active = false;
    };
  }, [mode, projectId]);

  // The run is over: show what it found.
  useEffect(() => {
    if (step === RUN && run && TERMINAL.includes(run.status) && !running) {
      setStep(RESULTS);
      setReached(RESULTS);
    }
  }, [step, run, running]);

  const selectedCount = useMemo(
    () => DEFINITION_KINDS.reduce((n, k) => n + (selected[k]?.size ?? 0), 0),
    [selected]
  );
  const hasInput = source === "text" ? text.trim().length > 0 : files.length > 0;
  const analysisReady =
    mode === "default" ||
    (mode === "project" && !!projectId && !!definitions && selectedCount > 0) ||
    (mode === "new" && newProject.name.trim().length > 0 && newProject.labels.size > 0);
  const busy = running || uploading;
  // Setting up or running: the results are done, leaving them loses nothing.
  useUnsavedWork(
    busy || step === RUN || (step !== RESULTS && (hasInput || mode === "new" || step === ANALYSIS))
  );

  const launch = async () => {
    setFormError(null);
    setStep(RUN);
    setReached(RUN);
    reset();
    try {
      let pid = "";
      let body = {};
      if (mode === "project") {
        pid = projectId;
        body = Object.fromEntries(DEFINITION_KINDS.map((k) => [BODY_FIELD[k], [...selected[k]]]));
      } else if (mode === "new") {
        // Make the project once; going back and forth reuses it.
        const key = `${newProject.name.trim()}|${[...newProject.labels].sort().join(",")}`;
        if (created.current?.key !== key) {
          const project = await createProject({ name: newProject.name.trim() });
          const entityIds = [];
          for (const label of newProject.labels)
            entityIds.push((await createDefinition(project.id, "entities", entityPayload(label))).id);
          created.current = { key, id: project.id, entityIds };
          setProjects((list) => [...(list ?? []), project]);
        }
        pid = created.current.id;
        body = {
          entity_ids: created.current.entityIds,
          relation_ids: [],
          classification_ids: [],
          safety_ids: [],
        };
      }
      body.anonymize = options.anonymize;
      if (source === "text") {
        body.text = text;
        setSent({ kind: "text", pages: textToPages(text) });
      } else {
        setSent({ kind: "files" });
        setUploading(true);
        const uploaded = [];
        for (const file of files) uploaded.push(await uploadFile(file));
        body.file_ids = uploaded.map((f) => f.id);
        body.blur_screenshots = options.blur;
        body.classify_images = options.classifyImages;
        setUploading(false);
      }
      await start(pid, body);
    } catch (err) {
      setUploading(false);
      setFormError(err.message);
    }
  };

  const restart = () => {
    reset();
    setText("");
    setFiles([]);
    setSent(null);
    setStep(SOURCE);
    setReached(SOURCE);
  };

  if (loadError && !projects) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!projects) return <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />;

  const titles = [
    ["wiz.source.title", "wiz.source.desc"],
    ["wiz.analysis.title", "wiz.analysis.desc"],
    ["wiz.run.title", "wiz.run.desc"],
    ["wiz.results.title", "wiz.results.desc"],
  ][step];
  const labels = ["wiz.step.source", "wiz.step.analysis", "wiz.step.run", "wiz.step.results"].map(t);
  const failed = step === RUN && !busy && (formError || error);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Stepper
        steps={labels}
        current={step}
        reached={reached}
        canGo={!busy}
        onGo={(i) => setStep(i)}
      />

      <Card>
        <CardHeader>
          <CardTitle>{t(titles[0])}</CardTitle>
          <CardDescription>{t(titles[1])}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {step === SOURCE && (
            <StepSource
              source={source}
              onSource={setSource}
              text={text}
              onText={setText}
              files={files}
              onFiles={setFiles}
            />
          )}
          {step === ANALYSIS && (
            <StepAnalysis
              mode={mode}
              onMode={setMode}
              projects={projects}
              projectId={projectId}
              onProject={setProjectId}
              definitions={definitions}
              selected={selected}
              onSelected={setSelected}
              newProject={newProject}
              onNewProject={setNewProject}
              isFile={source === "file"}
              options={options}
              onOptions={setOptions}
            />
          )}
          {step === RUN && <StepRun run={run} uploading={uploading} error={formError || error} />}
          {step === RESULTS && run && <StepResults run={run} source={sent} />}

          <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
            {step === SOURCE && <span />}
            {step === ANALYSIS && (
              <Button variant="outline" onClick={() => setStep(SOURCE)}>
                <ArrowLeft className="h-4 w-4" />
                {t("wiz.back")}
              </Button>
            )}
            {step === RUN && (
              <Button variant="outline" disabled={busy && !failed} onClick={() => setStep(ANALYSIS)}>
                <ArrowLeft className="h-4 w-4" />
                {t("wiz.back")}
              </Button>
            )}
            {step === RESULTS && (
              <Button variant="outline" onClick={() => setStep(ANALYSIS)}>
                <ArrowLeft className="h-4 w-4" />
                {t("wiz.tweak")}
              </Button>
            )}

            {step === SOURCE && (
              <Button disabled={!hasInput} onClick={() => setStep(ANALYSIS)}>
                {t("wiz.next")}
                <ArrowRight className="h-4 w-4" />
              </Button>
            )}
            {step === ANALYSIS && (
              <Button disabled={!analysisReady || busy} onClick={launch}>
                <Play className="h-4 w-4" />
                {t("wiz.launch")}
              </Button>
            )}
            {step === RUN && failed && (
              <Button onClick={launch}>
                <RotateCcw className="h-4 w-4" />
                {t("wiz.retry")}
              </Button>
            )}
            {step === RESULTS && (
              <Button onClick={restart}>
                <RotateCcw className="h-4 w-4" />
                {t("wiz.results.new")}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
