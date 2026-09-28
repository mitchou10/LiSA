import { useState } from "react";
import { Check, X, ShieldAlert, ShieldCheck, ChevronLeft, ChevronRight, Pencil, MousePointer2 } from "lucide-react";
import { Badge } from "../ui/badge";
import { cn } from "../../lib/utils";
import { useI18n } from "../../lib/i18n.jsx";
import { BBOX_LABELS } from "../../lib/mockResults";

const SEVERITY_COLOR = {
  high: "#ef4444",
  medium: "#f59e0b",
  low: "#3b82f6",
};

/**
 * Document result view: renders pages with bbox overlays, page-level
 * multi-label classification, and per-bbox validation. Also allows the
 * user to draw new bboxes and assign classifications (draw mode).
 */
export default function DocumentResultView({ result, onBboxDecision, onAddBbox, onUpdateBbox, canAnnotate = true }) {
  const { t } = useI18n();
  const [pageIndex, setPageIndex] = useState(0);
  const [drawMode, setDrawMode] = useState(false);
  const [activeBboxId, setActiveBboxId] = useState(null);

  const pages = result?.pages || [];
  const page = pages[pageIndex];

  if (!page) {
    return (
      <div className="rounded-lg border border-border p-8 text-center text-sm text-muted-foreground">
        {t("results.noPages")}
      </div>
    );
  }

  const totalDetections = pages.reduce(
    (acc, p) => acc + (p.bboxes?.length || 0),
    0
  );
  const flagged = pages.reduce(
    (acc, p) =>
      acc + (p.bboxes?.filter((b) => b.decision !== "rejected").length || 0),
    0
  );

  const activeBbox = activeBboxId
    ? page.bboxes?.find((b) => b.id === activeBboxId)
    : null;

  return (
    <div className="flex flex-col gap-4">
      {/* Summary banner */}
      <div
        className={cn(
          "rounded-lg border p-4",
          flagged > 0
            ? "border-destructive/50 bg-destructive/10"
            : "border-success/50 bg-success/10"
        )}
      >
        <div className="flex items-center gap-3">
          {flagged > 0 ? (
            <ShieldAlert className="h-6 w-6 shrink-0 text-destructive" />
          ) : (
            <ShieldCheck className="h-6 w-6 shrink-0 text-success" />
          )}
          <div className="min-w-0 flex-1">
            <p
              className={cn(
                "font-semibold",
                flagged > 0 ? "text-destructive" : "text-success"
              )}
            >
              {flagged > 0
                ? t("results.verdict.danger")
                : t("results.verdict.safe")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("results.docSummary")
                .replace("{flagged}", flagged)
                .replace("{total}", totalDetections)
                .replace("{pages}", pages.length)}
            </p>
          </div>
          {result?.metadata?.mock && <Badge variant="muted">mock</Badge>}
        </div>
      </div>

      {/* Page navigation + draw toggle */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPageIndex((i) => Math.max(0, i - 1))}
            disabled={pageIndex === 0}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border disabled:opacity-40"
            aria-label={t("results.prevPage")}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm font-medium tabular-nums">
            {t("results.pageOf")
              .replace("{current}", pageIndex + 1)
              .replace("{total}", pages.length)}
          </span>
          <button
            type="button"
            onClick={() =>
              setPageIndex((i) => Math.min(pages.length - 1, i + 1))
            }
            disabled={pageIndex >= pages.length - 1}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border disabled:opacity-40"
            aria-label={t("results.nextPage")}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
        <button
          type="button"
          onClick={() => canAnnotate && setDrawMode((d) => !d)}
          disabled={!canAnnotate}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
            !canAnnotate && "cursor-not-allowed opacity-40",
            canAnnotate && (drawMode
              ? "border-primary bg-primary/10 text-primary"
              : "border-border hover:bg-background/60")
          )}
        >
          {drawMode ? <Pencil className="h-4 w-4" /> : <MousePointer2 className="h-4 w-4" />}
          {drawMode ? t("results.drawMode") : t("results.selectMode")}
        </button>
      </div>

      {/* Page-level multi-label classification */}
      <div className="rounded-lg border border-border bg-background/40 p-4">
        <p className="mb-2 text-xs font-medium text-muted-foreground">
          {t("results.pageClassification")}
        </p>
        <div className="flex flex-wrap gap-2">
          {page.classifications?.map((c, i) => (
            <div
              key={`cls-${i}-${c.label}`}
              className="flex items-center gap-2 rounded-lg border border-border bg-background/60 px-3 py-1.5 text-sm"
            >
              <span className="font-medium">{c.label}</span>
              <span className="text-xs tabular-nums text-muted-foreground">
                {Math.round(c.probability * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Page canvas with bboxes */}
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <BboxCanvas
          page={page}
          drawMode={drawMode}
          activeBboxId={activeBboxId}
          onSelectBbox={setActiveBboxId}
          onAddBbox={(bbox) => {
            onAddBbox?.(pageIndex, bbox);
            setDrawMode(false);
          }}
          onUpdateBbox={(bboxId, patch) =>
            onUpdateBbox?.(pageIndex, bboxId, patch)
          }
          t={t}
        />
      </div>

      {/* Active bbox detail panel */}
      {activeBbox && (
        <BboxDetail
          bbox={activeBbox}
          onDecision={(decision) =>
            onBboxDecision?.(pageIndex, activeBbox.id, decision)
          }
          onUpdateClassification={(classification) =>
            onUpdateBbox?.(pageIndex, activeBbox.id, { classification })
          }
          t={t}
        />
      )}

      {/* Bbox list for current page */}
      {page.bboxes?.length > 0 && (
        <div className="rounded-lg border border-border bg-background/40 p-4">
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            {t("results.bboxList")}
          </p>
          <div className="flex flex-col gap-1.5">
            {page.bboxes.map((b) => (
              <button
                key={b.id}
                type="button"
                onClick={() =>
                  setActiveBboxId(b.id === activeBboxId ? null : b.id)
                }
                className={cn(
                  "flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                  b.id === activeBboxId
                    ? "border-primary bg-primary/5"
                    : "border-border bg-background/40 hover:bg-background/70"
                )}
              >
                <span
                  className="h-3 w-3 shrink-0 rounded-sm"
                  style={{ backgroundColor: b.color }}
                />
                <span className="flex-1 truncate font-medium">
                  {b.classification}
                </span>
                <span className="text-xs text-muted-foreground">
                  {Math.round(b.probability * 100)}%
                </span>
                {b.decision === "validated" && (
                  <Check className="h-3.5 w-3.5 text-green-500" />
                )}
                {b.decision === "rejected" && (
                  <X className="h-3.5 w-3.5 text-destructive" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Bbox canvas (render + draw) ────────────────────────────────────────────

function BboxCanvas({
  page,
  drawMode,
  activeBboxId,
  onSelectBbox,
  onAddBbox,
  onUpdateBbox,
  t,
}) {
  const [drawing, setDrawing] = useState(null);
  const [draftLabel, setDraftLabel] = useState(BBOX_LABELS[0].label);

  const handleMouseDown = (e) => {
    if (!drawMode) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const scaleX = page.width / rect.width;
    const scaleY = page.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    setDrawing({ x, y, w: 0, h: 0, scaleX, scaleY, rect });
  };

  const handleMouseMove = (e) => {
    if (!drawing) return;
    const scaleX = drawing.scaleX;
    const scaleY = drawing.scaleY;
    const x = (e.clientX - drawing.rect.left) * scaleX;
    const y = (e.clientY - drawing.rect.top) * scaleY;
    setDrawing((d) => ({
      ...d,
      w: x - d.x,
      h: y - d.y,
    }));
  };

  const handleMouseUp = () => {
    if (!drawing) return;
    const w = Math.abs(drawing.w);
    const h = Math.abs(drawing.h);
    if (w > 10 && h > 10) {
      const x = drawing.w < 0 ? drawing.x + drawing.w : drawing.x;
      const y = drawing.h < 0 ? drawing.y + drawing.h : drawing.y;
      onAddBbox({
        id: `bbox-drawn-${Date.now()}`,
        x,
        y,
        width: w,
        height: h,
        classification: draftLabel,
        color:
          BBOX_LABELS.find((l) => l.label === draftLabel)?.color || "#6b7280",
        description: t("results.drawnBboxDesc"),
        probability: 1.0,
        severity: "low",
        proposals: [],
        decision: null,
        drawn: true,
      });
    }
    setDrawing(null);
  };

  return (
    <div className="flex flex-col gap-3">
      {/* Draw mode toolbar */}
      {drawMode && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 p-2">
          <span className="text-xs font-medium text-muted-foreground">
            {t("results.drawLabel")}
          </span>
          <div className="flex flex-wrap gap-1">
            {BBOX_LABELS.map((l) => (
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

      {/* Page surface */}
      <div
        role="application"
        aria-label={t("results.pagePlaceholder").replace("{n}", page.page_number)}
        tabIndex={0}
        className="relative mx-auto bg-white shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        style={{
          width: "100%",
          maxWidth: `${page.width}px`,
          aspectRatio: `${page.width} / ${page.height}`,
          cursor: drawMode ? "crosshair" : "default",
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {/* Placeholder page content */}
        <div className="absolute inset-0 flex items-center justify-center text-xs text-gray-400">
          {t("results.pagePlaceholder").replace("{n}", page.page_number)}
        </div>

        {/* Bboxes */}
        {page.bboxes?.map((b) => {
          const isActive = b.id === activeBboxId;
          const isRejected = b.decision === "rejected";
          const isValidated = b.decision === "validated";
          return (
            <div
              key={b.id}
              role="button"
              tabIndex={0}
              onClick={(e) => {
                if (drawMode) return;
                e.stopPropagation();
                onSelectBbox(b.id === activeBboxId ? null : b.id);
              }}
              onKeyDown={(e) => {
                if (drawMode) return;
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  onSelectBbox(b.id === activeBboxId ? null : b.id);
                }
              }}
              className={cn(
                "absolute border-2 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isRejected && "opacity-40",
                !drawMode && "cursor-pointer hover:brightness-110"
              )}
              style={{
                left: `${(b.x / page.width) * 100}%`,
                top: `${(b.y / page.height) * 100}%`,
                width: `${(b.width / page.width) * 100}%`,
                height: `${(b.height / page.height) * 100}%`,
                borderColor: b.color,
                backgroundColor: `${b.color}22`,
                boxShadow: isActive
                  ? `0 0 0 2px ${b.color}, 0 0 0 4px white`
                  : undefined,
              }}
            >
              <span
                className="absolute -top-5 left-0 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-medium text-white"
                style={{ backgroundColor: b.color }}
              >
                {b.classification}
                {isValidated && " ✓"}
                {isRejected && " ✕"}
              </span>
            </div>
          );
        })}

        {/* Drawing preview */}
        {drawing && (
          <div
            className="absolute border-2 border-dashed border-primary bg-primary/10"
            style={{
              left: `${(Math.min(drawing.x, drawing.x + drawing.w) / page.width) * 100}%`,
              top: `${(Math.min(drawing.y, drawing.y + drawing.h) / page.height) * 100}%`,
              width: `${(Math.abs(drawing.w) / page.width) * 100}%`,
              height: `${(Math.abs(drawing.h) / page.height) * 100}%`,
            }}
          />
        )}
      </div>
    </div>
  );
}

// ── Bbox detail panel ───────────────────────────────────────────────────────

function BboxDetail({ bbox, onDecision, onUpdateClassification, t }) {
  return (
    <div className="rounded-lg border border-primary/40 bg-primary/5 p-4">
      <div className="flex items-center gap-2">
        <span
          className="h-3 w-3 rounded-sm"
          style={{ backgroundColor: bbox.color }}
        />
        <Badge variant="muted">{bbox.classification}</Badge>
        <span className="text-xs text-muted-foreground">
          {Math.round(bbox.probability * 100)}% {t("results.confidence")}
        </span>
        {bbox.drawn && <Badge variant="muted">{t("results.drawn")}</Badge>}
      </div>

      <p className="mt-2 text-sm text-muted-foreground">
        {bbox.description}
      </p>

      <p className="mt-2 text-xs text-muted-foreground">
        <code className="text-foreground">
          x={Math.round(bbox.x)}, y={Math.round(bbox.y)}, w=
          {Math.round(bbox.width)}, h={Math.round(bbox.height)}
        </code>
      </p>

      {/* Proposals */}
      {bbox.proposals?.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-xs font-medium text-muted-foreground">
            {t("results.proposals")}
          </p>
          <div className="flex flex-col gap-1.5">
            {bbox.proposals.map((p, i) => (
              <button
                key={`prop-${i}-${p.label}`}
                type="button"
                onClick={() => onUpdateClassification(p.label)}
                className="flex items-center gap-2 rounded-md border border-border bg-background/40 px-3 py-1.5 text-sm transition-colors hover:border-primary/50 hover:bg-primary/5"
              >
                <span className="flex-1 text-left">{p.label}</span>
                <span className="text-xs font-semibold tabular-nums text-muted-foreground">
                  {Math.round(p.probability * 100)}%
                </span>
              </button>
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
          {BBOX_LABELS.map((l) => (
            <button
              key={l.label}
              type="button"
              onClick={() => onUpdateClassification(l.label)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors",
                bbox.classification === l.label
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
          onClick={() => onDecision("validated")}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
            bbox.decision === "validated"
              ? "border-green-500 bg-green-500/10 text-green-600"
              : "border-border hover:border-green-500/50 hover:bg-green-500/5"
          )}
        >
          <Check className="h-4 w-4" />
          {t("results.validate")}
        </button>
        <button
          type="button"
          onClick={() => onDecision("rejected")}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
            bbox.decision === "rejected"
              ? "border-destructive bg-destructive/10 text-destructive"
              : "border-border hover:border-destructive/50 hover:bg-destructive/5"
          )}
        >
          <X className="h-4 w-4" />
          {t("results.reject")}
        </button>
      </div>
    </div>
  );
}
