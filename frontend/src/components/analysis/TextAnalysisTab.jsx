import { useState } from "react";
import { Play, Loader2 } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import ServiceSelector from "../../components/analysis/ServiceSelector";
import AnalysisPanel from "../../components/analysis/AnalysisPanel";
import TextResultView from "../../components/results/TextResultView";
import Results from "../../Results";
import { useAnalysis } from "../../hooks/useAnalysis";
import { useI18n } from "../../lib/i18n.jsx";
import { mockTextAnalysis, mockPredictSpan } from "../../lib/mockResults";
import { adaptBackendToTextResult } from "../../lib/resultAdapter";

/**
 * Text analysis tab: paste/type raw text and run the scanners on it.
 * Owns its own analysis state and results pane, independent from other tabs.
 */
export default function TextAnalysisTab() {
  const { t } = useI18n();
  const analysis = useAnalysis({
    mockFn: (inputData) => {
      const text = inputData.pages?.[0]?.content || "";
      return mockTextAnalysis(text);
    },
  });
  const [text, setText] = useState("");
  const [persist, setPersist] = useState(true);

  const hasInput = text.trim().length > 0;
  const canAnalyze = hasInput && analysis.selected.size > 0 && !analysis.running;

  const buildInputData = () => ({
    metadata: { source: "web", kind: "text" },
    pages: [{ content: text, page_number: 1 }],
  });

  const onKeyDown = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && canAnalyze) {
      analysis.analyze(buildInputData, t);
    }
  };

  const handleDecision = (spanId, decision) => {
    const result = analysis.result;
    if (!result?.spans) return;
    const spans = result.spans.map((s) =>
      s.id === spanId ? { ...s, decision } : s
    );
    analysis.setMockResult({ ...result, spans });
  };

  const handleAddSpan = (start, end, label) => {
    const result = analysis.result;
    if (!result?.text) return;
    const span = mockPredictSpan(result.text, start, end, label);
    const spans = [...(result.spans || []), span];
    analysis.setMockResult({ ...result, spans });
  };

  const handleUpdateSpan = (spanId, patch) => {
    const result = analysis.result;
    if (!result?.spans) return;
    const spans = result.spans.map((s) =>
      s.id === spanId ? { ...s, ...patch } : s
    );
    analysis.setMockResult({ ...result, spans });
  };

  return (
    <AnalysisPanel
      analysis={analysis}
      inputTitleKey="analyze.input.title"
      inputDescKey="analyze.input.desc"
      ResultComponent={TextResultAdapter}
      resultProps={{ onDecision: handleDecision, onAddSpan: handleAddSpan, onUpdateSpan: handleUpdateSpan, canAnnotate: persist, originalText: text }}
    >
      <div className="flex flex-col gap-4">
        <Textarea
          rows={10}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={t("analyze.text.placeholder")}
          className="font-sans"
        />

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
          <Button
            onClick={() => analysis.analyze(buildInputData, t)}
            disabled={!canAnalyze}
          >
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
      </div>
    </AnalysisPanel>
  );
}

/**
 * Renders TextResultView when a rich result (with spans) is available,
 * and falls back to the legacy Results component for raw backend output
 * that can't be adapted.
 */
function TextResultAdapter({ result, loading, error, onDecision, onAddSpan, onUpdateSpan, canAnnotate, originalText }) {
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

  // Rich mock result (text spans) → dedicated view
  if (result.kind === "text" || result.spans) {
    return (
      <TextResultView
        result={result}
        onDecision={onDecision}
        onAddSpan={onAddSpan}
        onUpdateSpan={onUpdateSpan}
        canAnnotate={canAnnotate}
      />
    );
  }

  // Backend Analyse result (pages/detections) → try to adapt to text spans
  if (result.pages && originalText) {
    const adapted = adaptBackendToTextResult(result, originalText);
    if (adapted) {
      return (
        <TextResultView
          result={adapted}
          onDecision={onDecision}
          onAddSpan={onAddSpan}
          onUpdateSpan={onUpdateSpan}
          canAnnotate={canAnnotate}
        />
      );
    }
  }

  // Legacy backend result → default Results component
  return <Results result={result} loading={loading} error={error} />;
}
