import { useMemo, useState, useRef } from "react";
import { Check, X, ShieldAlert, ShieldCheck, ChevronDown, Pencil, MousePointer2 } from "lucide-react";
import { Badge } from "../ui/badge";
import { cn } from "../../lib/utils";
import { useI18n } from "../../lib/i18n.jsx";
import { TEXT_LABELS } from "../../lib/mockResults";

const SEVERITY_COLOR = {
  high: "bg-red-500/20 text-red-700 dark:text-red-400",
  medium: "bg-amber-500/20 text-amber-700 dark:text-amber-400",
  low: "bg-blue-500/20 text-blue-700 dark:text-blue-400",
};

const SEVERITY_UNDERLINE = {
  high: "decoration-red-500",
  medium: "decoration-amber-500",
  low: "decoration-blue-500",
};

function severityDotClass(severity) {
  if (severity === "high") return "bg-red-500";
  if (severity === "medium") return "bg-amber-500";
  return "bg-blue-500";
}

/**
 * Render the analyzed text with highlighted spans. Clicking a span opens
 * the detail panel where the user can validate / reject the classification
 * and see alternative proposals with probabilities.
 *
 * In annotate mode the user can select raw text to create a new span;
 * predictions are generated for the selected segment.
 */
export default function TextResultView({ result, onDecision, onAddSpan, onUpdateSpan, canAnnotate = true }) {
  const { t } = useI18n();
  const [activeId, setActiveId] = useState(null);
  const [annotateMode, setAnnotateMode] = useState(false);
  const [draftLabel, setDraftLabel] = useState(TEXT_LABELS[0].label);
  const textRef = useRef(null);

  const segments = useMemo(() => {
    if (!result?.text || !result?.spans?.length) {
      return [{ type: "text", content: result?.text || "" }];
    }

    const sorted = [...result.spans].sort(
      (a, b) => a.start_char - b.start_char
    );
    const segs = [];
    let cursor = 0;
    for (const span of sorted) {
      if (span.start_char > cursor) {
        segs.push({
          type: "text",
          content: result.text.slice(cursor, span.start_char),
        });
      }
      segs.push({ type: "span", span });
      cursor = span.end_char;
    }
    if (cursor < result.text.length) {
      segs.push({ type: "text", content: result.text.slice(cursor) });
    }
    return segs;
  }, [result]);

  const spans = result?.spans || [];
  const flagged = spans.filter((s) => s.decision !== "rejected");
  const anyFlagged = flagged.length > 0;

  const activeSpan = activeId
    ? spans.find((s) => s.id === activeId)
    : null;

  const handleDecision = (spanId, decision) => {
    onDecision?.(spanId, decision);
  };

  const handleMouseUp = () => {
    if (!annotateMode) return;
    const el = textRef.current;
    if (!el) return;
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return;

    // Only consider selections inside our text container
    const range = sel.getRangeAt(0);
    if (!el.contains(range.commonAncestorContainer)) return;

    // Compute character offset by walking text nodes inside the container
    const start = charOffsetInContainer(el, range.startContainer, range.startOffset);
    const end = charOffsetInContainer(el, range.endContainer, range.endOffset);
    if (start === null || end === null || end <= start) return;

    // Skip if overlaps an existing span
    if (spans.some((s) => start < s.end_char && end > s.start_char)) {
      sel.removeAllRanges();
      return;
    }

    onAddSpan?.(start, end, draftLabel);
    sel.removeAllRanges();
    setAnnotateMode(false);
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Summary banner */}
      <div
        className={cn(
          "rounded-lg border p-4",
          anyFlagged
            ? "border-destructive/50 bg-destructive/10"
            : "border-success/50 bg-success/10"
        )}
      >
        <div className="flex items-center gap-3">
          {anyFlagged ? (
            <ShieldAlert className="h-6 w-6 shrink-0 text-destructive" />
          ) : (
            <ShieldCheck className="h-6 w-6 shrink-0 text-success" />
          )}
          <div className="min-w-0 flex-1">
            <p
              className={cn(
                "font-semibold",
                anyFlagged ? "text-destructive" : "text-success"
              )}
            >
              {anyFlagged
                ? t("results.verdict.danger")
                : t("results.verdict.safe")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("results.summary")
                .replace("{flagged}", flagged.length)
                .replace("{total}", spans.length)}
            </p>
          </div>
          {result?.metadata?.mock && <Badge variant="muted">mock</Badge>}
        </div>
      </div>

      {/* Annotate mode toggle */}
      <div className="flex items-center justify-end gap-2">
        {!canAnnotate && (
          <span className="text-xs text-muted-foreground">
            {t("results.persistHint")}
          </span>
        )}
        <button
          type="button"
          onClick={() => canAnnotate && setAnnotateMode((a) => !a)}
          disabled={!canAnnotate}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
            !canAnnotate && "cursor-not-allowed opacity-40",
            canAnnotate && (annotateMode
              ? "border-primary bg-primary/10 text-primary"
              : "border-border hover:bg-background/60")
          )}
        >
          {annotateMode ? <Pencil className="h-4 w-4" /> : <MousePointer2 className="h-4 w-4" />}
          {annotateMode ? t("results.annotateMode") : t("results.selectMode")}
        </button>
      </div>

      {/* Annotate mode toolbar */}
      {annotateMode && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 p-2">
          <span className="text-xs font-medium text-muted-foreground">
            {t("results.annotateLabel")}
          </span>
          <div className="flex flex-wrap gap-1">
            {TEXT_LABELS.map((l) => (
              <button
                key={l.label}
                type="button"
                onClick={() => setDraftLabel(l.label)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors",
                  draftLabel === l.label
                    ? "border-primary bg-primary/10"
                    : "border-border hover:bg-background/60"
                )}
              >
                <span
                  className="h-2 w-2 rounded-sm"
                  style={{ backgroundColor: l.color }}
                />
                {l.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Highlighted text */}
      <div className="rounded-lg border border-border bg-background/40 p-4">
        <p className="mb-2 text-xs font-medium text-muted-foreground">
          {annotateMode
            ? t("results.annotateHint")
            : t("results.highlightedText")}
        </p>
        <p
          ref={textRef}
          onMouseUp={handleMouseUp}
          className={cn(
            "whitespace-pre-wrap wrap-break-word text-sm leading-relaxed",
            annotateMode && "cursor-text"
          )}
        >
          {segments.map((seg, i) => {
            if (seg.type === "text")
              return <span key={`txt-${i}`}>{seg.content}</span>;
            const s = seg.span;
            const isActive = s.id === activeId;
            const isRejected = s.decision === "rejected";
            const isValidated = s.decision === "validated";
            return (
              <span
                key={s.id}
                role="button"
                tabIndex={0}
                onClick={() => setActiveId(isActive ? null : s.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setActiveId(isActive ? null : s.id);
                  }
                }}
                className={cn(
                  "cursor-pointer rounded px-0.5 underline decoration-2 underline-offset-2 transition-colors focus:outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
                  SEVERITY_COLOR[s.severity] || SEVERITY_COLOR.low,
                  SEVERITY_UNDERLINE[s.severity] || SEVERITY_UNDERLINE.low,
                  isActive && "ring-2 ring-ring ring-offset-1",
                  isRejected && "opacity-40 line-through",
                  isValidated && "ring-2 ring-green-500 ring-offset-1"
                )}
              >
                {s.text}
              </span>
            );
          })}
        </p>
      </div>

      {/* Span detail panel */}
      {activeSpan && (
        <div className="rounded-lg border border-primary/40 bg-primary/5 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <Badge variant={activeSpan.severity === "high" ? "destructive" : "muted"}>
                  {activeSpan.label}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {Math.round(activeSpan.probability * 100)}% {t("results.confidence")}
                </span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {activeSpan.description}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                <code className="text-foreground">
                  [{activeSpan.start_char}–{activeSpan.end_char}]
                </code>
                {" : "}
                <code className="text-foreground">{activeSpan.text}</code>
              </p>
            </div>
          </div>

          {/* Proposals */}
          {activeSpan.proposals?.length > 0 && (
            <div className="mt-3">
              <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                {t("results.proposals")}
              </p>
              <div className="flex flex-col gap-1.5">
                {activeSpan.proposals.map((p, i) => (
                  <div
                    key={`prop-${i}-${p.label}`}
                    className="flex items-center gap-2 rounded-md border border-border bg-background/40 px-3 py-1.5 text-sm"
                  >
                    <span className="flex-1">{p.label}</span>
                    <span className="text-xs font-semibold tabular-nums text-muted-foreground">
                      {Math.round(p.probability * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Manual classification change */}
          <div className="mt-3">
            <p className="mb-1.5 text-xs font-medium text-muted-foreground">
              {t("results.changeClassification")}
            </p>
            <div className="flex flex-wrap gap-1">
              {TEXT_LABELS.map((l) => (
                <button
                  key={l.label}
                  type="button"
                  onClick={() => onUpdateSpan?.(activeSpan.id, { label: l.label, classification: l.label.toLowerCase().replace(/\s+/g, "_"), severity: l.severity })}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors",
                    activeSpan.label === l.label
                      ? "border-primary bg-primary/10"
                      : "border-border hover:bg-background/60"
                  )}
                >
                  <span
                    className="h-2 w-2 rounded-sm"
                    style={{ backgroundColor: l.color }}
                  />
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          {/* Validate / Reject */}
          <div className="mt-4 flex items-center gap-2">
            <button
              type="button"
              onClick={() => handleDecision(activeSpan.id, "validated")}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
                activeSpan.decision === "validated"
                  ? "border-green-500 bg-green-500/10 text-green-600"
                  : "border-border hover:border-green-500/50 hover:bg-green-500/5"
              )}
            >
              <Check className="h-4 w-4" />
              {t("results.validate")}
            </button>
            <button
              type="button"
              onClick={() => handleDecision(activeSpan.id, "rejected")}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
                activeSpan.decision === "rejected"
                  ? "border-destructive bg-destructive/10 text-destructive"
                  : "border-border hover:border-destructive/50 hover:bg-destructive/5"
              )}
            >
              <X className="h-4 w-4" />
              {t("results.reject")}
            </button>
          </div>
        </div>
      )}

      {/* All spans list (collapsible) */}
      {spans.length > 0 && (
        <SpanList
          spans={spans}
          activeId={activeId}
          onSelect={setActiveId}
          t={t}
        />
      )}
    </div>
  );
}

function SpanList({ spans, activeId, onSelect, t }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-lg border border-border bg-background/40 px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <span>
          {t("results.spansCount").replace("{n}", spans.length)}
        </span>
        <ChevronDown
          className={cn("h-4 w-4 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <div className="mt-3 flex flex-col gap-1.5">
          {spans.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onSelect(s.id)}
              className={cn(
                "flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                s.id === activeId
                  ? "border-primary bg-primary/5"
                  : "border-border bg-background/40 hover:bg-background/70"
              )}
            >
              <span
                className={cn(
                  "h-2 w-2 shrink-0 rounded-full",
                  severityDotClass(s.severity)
                )}
              />
              <span className="flex-1 truncate font-medium">{s.label}</span>
              <span className="text-xs text-muted-foreground">
                {Math.round(s.probability * 100)}%
              </span>
              {s.decision === "validated" && (
                <Check className="h-3.5 w-3.5 text-green-500" />
              )}
              {s.decision === "rejected" && (
                <X className="h-3.5 w-3.5 text-destructive" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Compute the character offset of (node, offset) relative to the container
 * element, by walking its text nodes. Returns null if the node is not found.
 */
function charOffsetInContainer(container, node, offset) {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let total = 0;
  let current = walker.nextNode();
  while (current) {
    if (current === node) {
      return total + offset;
    }
    total += current.textContent.length;
    current = walker.nextNode();
  }
  return null;
}
