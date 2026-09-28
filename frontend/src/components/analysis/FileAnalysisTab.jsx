import { useRef, useState } from "react";
import { Upload, File as FileIcon, Play, Loader2, X } from "lucide-react";
import { Button } from "../../components/ui/button";
import ServiceSelector from "../../components/analysis/ServiceSelector";
import AnalysisPanel from "../../components/analysis/AnalysisPanel";
import DocumentResultView from "../../components/results/DocumentResultView";
import Results from "../../Results";
import { useAnalysis } from "../../hooks/useAnalysis";
import { useI18n } from "../../lib/i18n.jsx";
import { cn } from "../../lib/utils";
import { mockDocumentAnalysis, BBOX_LABELS } from "../../lib/mockResults";

const ACCEPTED = ".txt,.md,.json,.csv,.log,.html,.xml,.yaml,.yml";

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * File analysis tab: drop or pick one or more files, their textual content
 * is extracted client-side and sent to the scanners as pages.
 * Owns its own analysis state and results pane, independent from other tabs.
 */
export default function FileAnalysisTab() {
  const { t } = useI18n();
  const analysis = useAnalysis({
    mockFn: (inputData) => mockDocumentAnalysis(inputData),
  });
  const inputRef = useRef(null);
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [persist, setPersist] = useState(true);

  const canAnalyze =
    files.length > 0 && analysis.selected.size > 0 && !analysis.running;

  const addFiles = (incoming) => {
    const next = [...files];
    for (const f of Array.from(incoming)) {
      if (next.some((x) => x.name === f.name && x.size === f.size)) continue;
      next.push(f);
    }
    setFiles(next);
  };

  const removeFile = (idx) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer?.files?.length) addFiles(e.dataTransfer.files);
  };

  const buildInputData = async () => {
    const pages = [];
    let i = 0;
    for (const f of files) {
      let content;
      // Read as text; binary files will yield best-effort text.
      try {
        content = await f.text();
      } catch {
        content = "";
      }
      pages.push({
        content: content || "",
        page_number: ++i,
        metadata: { filename: f.name, size: f.size, type: f.type || "unknown" },
      });
    }
    return {
      metadata: { source: "web", kind: "file" },
      pages,
    };
  };

  const onAnalyze = async () => {
    const data = await buildInputData();
    analysis.analyze(() => data, t);
  };

  const onKeyDown = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && canAnalyze) {
      onAnalyze();
    }
  };

  const handleBboxDecision = (pageIndex, bboxId, decision) => {
    const result = analysis.result;
    if (!result?.pages) return;
    const pages = result.pages.map((p, i) =>
      i === pageIndex
        ? {
            ...p,
            bboxes: (p.bboxes || []).map((b) =>
              b.id === bboxId ? { ...b, decision } : b
            ),
          }
        : p
    );
    analysis.setMockResult({ ...result, pages });
  };

  const handleAddBbox = (pageIndex, bbox) => {
    const result = analysis.result;
    if (!result?.pages) return;
    const pages = result.pages.map((p, i) =>
      i === pageIndex
        ? { ...p, bboxes: [...(p.bboxes || []), bbox] }
        : p
    );
    analysis.setMockResult({ ...result, pages });
  };

  const handleUpdateBbox = (pageIndex, bboxId, patch) => {
    const result = analysis.result;
    if (!result?.pages) return;
    const pages = result.pages.map((p, i) =>
      i === pageIndex
        ? {
            ...p,
            bboxes: (p.bboxes || []).map((b) =>
              b.id === bboxId
                ? {
                    ...b,
                    ...patch,
                    color:
                      patch.classification != null
                        ? BBOX_LABELS.find((l) => l.label === patch.classification)
                            ?.color || b.color
                        : b.color,
                  }
                : b
            ),
          }
        : p
    );
    analysis.setMockResult({ ...result, pages });
  };

  return (
    <AnalysisPanel
      analysis={analysis}
      inputTitleKey="analyze.file.input.title"
      inputDescKey="analyze.file.input.desc"
      ResultComponent={DocumentResultAdapter}
      resultProps={{
        onBboxDecision: handleBboxDecision,
        onAddBbox: handleAddBbox,
        onUpdateBbox: handleUpdateBbox,
        canAnnotate: persist,
      }}
    >
      <section
        className="flex flex-col gap-4"
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onKeyDown={onKeyDown}
      >
        {/* Dropzone */}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors",
            dragging
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50 hover:bg-muted/40"
          )}
        >
          <Upload className="h-6 w-6 text-muted-foreground" />
          <span className="text-sm font-medium">
            {t("analyze.file.drop")}
          </span>
          <span className="text-xs text-muted-foreground">
            {t("analyze.file.formats")}
          </span>
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) addFiles(e.target.files);
            e.target.value = "";
          }}
        />

        {/* File list */}
        {files.length > 0 && (
          <ul className="flex flex-col gap-1.5">
            {files.map((f, idx) => (
              <li
                key={`${f.name}-${idx}`}
                className="flex items-center gap-2.5 rounded-lg border border-border bg-background/40 px-3 py-2 text-sm"
              >
                <FileIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="flex-1 truncate font-medium">{f.name}</span>
                <span className="text-xs text-muted-foreground">
                  {formatBytes(f.size)}
                </span>
                <button
                  type="button"
                  onClick={() => removeFile(idx)}
                  className="text-muted-foreground hover:text-destructive"
                  aria-label={t("analyze.file.remove")}
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}

        <ServiceSelector
          services={analysis.services}
          selected={analysis.selected}
          onToggle={analysis.toggleService}
          onSelectAll={analysis.selectAll}
          onClearAll={analysis.clearAll}
        />

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={persist}
            onChange={(e) => setPersist(e.target.checked)}
            className="h-4 w-4 rounded border-border"
          />
          {t("results.persist")}
        </label>

        <div className="flex items-center gap-3">
          <Button onClick={onAnalyze} disabled={!canAnalyze}>
            {analysis.running ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {analysis.running
              ? t("analyze.running")
              : t("analyze.run.group").replace("{n}", analysis.selected.size)}
          </Button>
          <span className="text-xs text-muted-foreground">
            {t("analyze.shortcut")}
          </span>
        </div>
      </section>
    </AnalysisPanel>
  );
}

/**
 * Renders DocumentResultView when a rich mock result (with pages/bboxes) is
 * available, and falls back to the legacy Results component for real backend
 * output.
 */
function DocumentResultAdapter({
  result,
  loading,
  error,
  onBboxDecision,
  onAddBbox,
  onUpdateBbox,
  canAnnotate,
}) {
  const { t } = useI18n();

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        {error}
      </div>
    );
  }
  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border p-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t("analyze.running")}
      </div>
    );
  }
  if (!result) {
    return (
      <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        {t("results.empty")}
      </div>
    );
  }
  // Rich mock result (document pages/bboxes) → dedicated view
  if (result.kind === "document" || result.pages?.[0]?.bboxes) {
    return (
      <DocumentResultView
        result={result}
        onBboxDecision={onBboxDecision}
        onAddBbox={onAddBbox}
        onUpdateBbox={onUpdateBbox}
        canAnnotate={canAnnotate}
      />
    );
  }
  // Legacy backend result → default Results component
  return <Results result={result} loading={loading} error={error} />;
}
