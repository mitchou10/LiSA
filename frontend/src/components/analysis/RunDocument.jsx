import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Download,
  FileImage,
  FileText,
  ImageOff,
  Loader2,
  PencilRuler,
  Maximize2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { usePageImage } from "../../hooks/usePageImage";
import { usePageBboxes } from "../../hooks/usePageBboxes";
import { renderRunDocument } from "../../lib/api";
import { buildPages, colorFor, isAnonymizing, segments } from "../../lib/runModel";
import { cn } from "../../lib/utils";
import { useI18n } from "../../lib/i18n.jsx";

const HEAD_COLOR = "hsl(215 80% 50%)";
const TAIL_COLOR = "hsl(285 70% 50%)";
const ZOOM_MIN = 1;
const ZOOM_MAX = 5;
const clampZoom = (z) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(z * 100) / 100));
const pct = (n) => (n == null ? "" : `${Math.round(n * 100)}%`);

// Hide a text: every character but whitespace becomes "*", so lengths and
// offsets are unchanged and the shape of the text stays recognisable.
const mask = (text) => text.replace(/\S/g, "*");
const show = (text, masked) => (masked ? mask(text) : text);

// Every highlight of a page, as one list: what to draw, where, in what colour.
export function highlights(page, layers, masked) {
  const out = [];
  if (layers.entities)
    for (const e of page.entities)
      out.push({
        id: e.id,
        kind: "entity",
        title: `${show(e.text, masked)} · ${e.label} · ${e.category} · ${e.action} · ${pct(e.score)}`,
        text: e.text,
        label: e.label,
        color: colorFor(e.category),
        flagged: e.flagged,
        start: e.start,
        end: e.end,
        bboxes: e.bboxes,
      });
  if (layers.relations)
    for (const r of page.relations)
      for (const [side, end, color] of [
        ["head", r.head, HEAD_COLOR],
        ["tail", r.tail, TAIL_COLOR],
      ])
        out.push({
          id: `${r.id}-${side}`,
          relationId: r.id,
          kind: "relation",
          title: `${show(r.head.text, masked)} — ${r.relation} → ${show(r.tail.text, masked)} (${side})`,
          text: end.text,
          color,
          start: end.start,
          end: end.end,
          bboxes: end.bboxes,
        });
  return out;
}

/** The page screenshot with the boxes of every highlight drawn on it. */
export function PageImage({
  page,
  items,
  activeId,
  onActive,
  drawn = [],
  drawMode = false,
  onDraw,
  onDeleteDrawn,
}) {
  const { t } = useI18n();
  const { url, error, loading } = usePageImage(page.image);
  // The box being dragged, in fractions of the page.
  const [draft, setDraft] = useState(null);
  // 1 = the page fits the width; above, the page is wider and scrolls.
  const [zoom, setZoom] = useState(1);
  const scroller = useRef(null);

  // Ctrl/Cmd + wheel zooms toward the cursor (a plain wheel still scrolls).
  useEffect(() => {
    const el = scroller.current;
    if (!el) return undefined;
    const onWheel = (e) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const px = e.clientX - r.left;
      const py = e.clientY - r.top;
      setZoom((z) => {
        const next = clampZoom(z * (e.deltaY < 0 ? 1.15 : 1 / 1.15));
        const k = next / z;
        el.scrollLeft = (el.scrollLeft + px) * k - px;
        el.scrollTop = (el.scrollTop + py) * k - py;
        return next;
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [url]);

  const point = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
      y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
    };
  };
  const boxOf = (a, b) => ({
    x: Math.min(a.x, b.x),
    y: Math.min(a.y, b.y),
    width: Math.abs(a.x - b.x),
    height: Math.abs(a.y - b.y),
  });
  const startDraw = (e) => {
    if (!drawMode || e.target !== e.currentTarget) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    setDraft({ from: point(e), to: point(e) });
  };
  const moveDraw = (e) => draft && setDraft({ ...draft, to: point(e) });
  const endDraw = (e) => {
    if (!draft) return;
    const box = boxOf(draft.from, point(e));
    setDraft(null);
    // A click, not a drag: ignore it.
    if (box.width > 0.005 && box.height > 0.005) onDraw?.(box, url);
  };

  if (loading)
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-border">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  if (error)
    return (
      <div className="flex h-24 items-center justify-center gap-2 rounded-lg border border-dashed border-border text-sm text-muted-foreground">
        <ImageOff className="h-4 w-4" />
        {error === "gone" ? t("run.doc.imageGone") : error}
      </div>
    );
  if (!url) return null;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-end gap-1">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          title={t("run.doc.zoomOut")}
          disabled={zoom <= ZOOM_MIN}
          onClick={() => setZoom((z) => clampZoom(z - 0.5))}
        >
          <ZoomOut className="h-4 w-4" />
        </Button>
        <button
          type="button"
          title={t("run.doc.zoomFit")}
          onClick={() => setZoom(1)}
          className="w-12 text-center text-xs tabular-nums text-muted-foreground hover:text-foreground"
        >
          {Math.round(zoom * 100)}%
        </button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          title={t("run.doc.zoomIn")}
          disabled={zoom >= ZOOM_MAX}
          onClick={() => setZoom((z) => clampZoom(z + 0.5))}
        >
          <ZoomIn className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          title={t("run.doc.zoomFit")}
          disabled={zoom === 1}
          onClick={() => setZoom(1)}
        >
          <Maximize2 className="h-4 w-4" />
        </Button>
      </div>
      <div
        ref={scroller}
        className={cn(
          "rounded-lg border border-border",
          zoom > 1 ? "max-h-[75vh] overflow-auto" : "overflow-hidden"
        )}
      >
    <div
      className={cn("relative", drawMode && "cursor-crosshair touch-none")}
      style={{ width: `${zoom * 100}%` }}
      onPointerDown={startDraw}
      onPointerMove={moveDraw}
      onPointerUp={endDraw}
    >
      <img
        src={url}
        alt={`${t("run.page")} ${page.number}`}
        className="pointer-events-none block w-full select-none"
        draggable={false}
      />
      {drawn.map((b) => (
        <button
          type="button"
          key={b.id}
          title={[b.label, drawMode && t("run.doc.drawHint")].filter(Boolean).join(" · ")}
          disabled={!drawMode}
          onClick={() => onDeleteDrawn?.(b.id)}
          className="absolute border-2 border-neutral-900 bg-neutral-900/35 disabled:cursor-default"
          style={{
            ...(b.label ? { borderColor: colorFor(b.label) } : {}),
            left: `${b.x * 100}%`,
            top: `${b.y * 100}%`,
            width: `${b.width * 100}%`,
            height: `${b.height * 100}%`,
          }}
        />
      ))}
      {draft && (
        <div
          className="pointer-events-none absolute border-2 border-dashed border-neutral-900 bg-neutral-900/20"
          style={{
            left: `${boxOf(draft.from, draft.to).x * 100}%`,
            top: `${boxOf(draft.from, draft.to).y * 100}%`,
            width: `${boxOf(draft.from, draft.to).width * 100}%`,
            height: `${boxOf(draft.from, draft.to).height * 100}%`,
          }}
        />
      )}
      {items.flatMap((h) =>
        h.bboxes.map((b, i) => (
          <button
            type="button"
            key={`${h.id}-${i}`}
            title={h.title}
            onMouseEnter={() => onActive(h.id)}
            onMouseLeave={() => onActive(null)}
            className={cn(
              "absolute rounded-[2px] border-2 transition-all",
              h.kind === "relation" && "border-dashed",
              activeId === h.id && "z-10 ring-2 ring-offset-1"
            )}
            style={{
              left: `${b.x * 100}%`,
              top: `${b.y * 100}%`,
              width: `${b.width * 100}%`,
              height: `${b.height * 100}%`,
              borderColor: h.color,
              backgroundColor: `color-mix(in srgb, ${h.color} ${
                activeId === h.id ? 35 : 15
              }%, transparent)`,
              "--tw-ring-color": h.color,
            }}
          />
        ))
      )}
    </div>
      </div>
      <p className="text-xs text-muted-foreground">{t("run.doc.zoomHint")}</p>
    </div>
  );
}

/** The text the anonymize worker returned: stars, with a coloured [LABEL] per entity. */
export function AnonymizedText({ content, t }) {
  const parts = content.split(/(\[[^\]\n]+\])/);
  return (
    <div className="space-y-1">
      <p className="whitespace-pre-wrap rounded-lg border border-border bg-background/40 p-3 text-sm leading-relaxed">
        {parts.map((part, i) =>
          /^\[[^\]\n]+\]$/.test(part) ? (
            <mark
              key={i}
              className="rounded-[3px] px-1 font-medium text-foreground"
              style={{
                backgroundColor: `color-mix(in srgb, ${colorFor(part)} 30%, transparent)`,
              }}
            >
              {part}
            </mark>
          ) : (
            part
          )
        )}
      </p>
      <p className="text-xs text-muted-foreground">{t("run.doc.anonymized")}</p>
    </div>
  );
}

/** The page text with the spans marked: entities highlighted, relation ends underlined. */
export function PageText({ page, items, activeId, onActive, masked }) {
  const { t } = useI18n();
  const parts = useMemo(() => segments(page.content, items), [page.content, items]);
  if (!page.content.trim())
    return <p className="text-sm text-muted-foreground">{t("run.doc.noText")}</p>;
  return (
    <p className="whitespace-pre-wrap rounded-lg border border-border bg-background/40 p-3 text-sm leading-relaxed">
      {parts.map((part) => {
        if (part.spans.length === 0) return show(part.text, masked);
        const entity = part.spans.find((s) => s.kind === "entity");
        const relation = part.spans.find((s) => s.kind === "relation");
        const active = part.spans.some((s) => s.id === activeId);
        return (
          <mark
            key={part.start}
            title={part.spans.map((s) => s.title).join("\n")}
            onMouseEnter={() => onActive(part.spans[0].id)}
            onMouseLeave={() => onActive(null)}
            className="rounded-[3px] px-0.5 text-foreground"
            style={{
              backgroundColor: entity
                ? `color-mix(in srgb, ${entity.color} ${active ? 45 : 22}%, transparent)`
                : "transparent",
              textDecoration: relation ? "underline" : "none",
              textDecorationColor: relation?.color,
              textDecorationThickness: "2px",
              textUnderlineOffset: "3px",
            }}
          >
            {show(part.text, masked)}
          </mark>
        );
      })}
    </p>
  );
}

function Side({ page, activeId, onActive, layers, masked, selected, onToggle, t }) {
  return (
    <div className="space-y-4">
      {layers.entities && (
        <div className="space-y-1.5">
          <div className="text-sm font-medium">
            {t("run.step.ner")} ({page.entities.length})
          </div>
          {page.entities.length === 0 && (
            <p className="text-xs text-muted-foreground">{t("run.nothing")}</p>
          )}
          <ul className="space-y-1">
            {page.entities.map((e) => (
              <li
                key={e.id}
                onMouseEnter={() => onActive(e.id)}
                onMouseLeave={() => onActive(null)}
                className={cn(
                  "flex items-center gap-2 rounded-md border border-transparent px-2 py-1 text-sm",
                  activeId === e.id && "border-border bg-muted"
                )}
              >
                <input
                  type="checkbox"
                  className="shrink-0"
                  checked={selected.has(`${page.number}:${e.id}`)}
                  onChange={() => onToggle(`${page.number}:${e.id}`)}
                  title={t("run.doc.selectEntity")}
                />
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: colorFor(e.category) }}
                />
                <span className="min-w-0 flex-1 truncate font-medium">
                  {show(e.text, masked)}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">{e.label}</span>
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  {pct(e.score)}
                </span>
                <Badge variant={e.action === "block" ? "destructive" : "muted"}>
                  {t(`sensitive.action.${e.action}`)}
                </Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
      {layers.relations && (
        <div className="space-y-1.5">
          <div className="text-sm font-medium">
            {t("run.step.relation")} ({page.relations.length})
          </div>
          {page.relations.length === 0 && (
            <p className="text-xs text-muted-foreground">{t("run.nothing")}</p>
          )}
          <ul className="space-y-1">
            {page.relations.map((r) => (
              <li
                key={r.id}
                onMouseEnter={() => onActive(`${r.id}-head`)}
                onMouseLeave={() => onActive(null)}
                className={cn(
                  "flex flex-wrap items-center gap-1.5 rounded-md border border-transparent px-2 py-1 text-sm",
                  activeId?.startsWith(r.id) && "border-border bg-muted"
                )}
              >
                <span className="font-medium" style={{ color: HEAD_COLOR }}>
                  {show(r.head.text, masked)}
                </span>
                <span className="text-xs text-muted-foreground">— {r.relation} →</span>
                <span className="font-medium" style={{ color: TAIL_COLOR }}>
                  {show(r.tail.text, masked)}
                </span>
                <span
                  className="text-xs tabular-nums text-muted-foreground"
                  title={`${t("run.doc.head")} ${pct(r.head.score)} · ${t("run.doc.tail")} ${pct(r.tail.score)}`}
                >
                  {pct(r.score)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * The export bar: pick what to blur, which entities, and download the pages
 * as PNG (the current page), ZIP or PDF (every page). Only shown for runs
 * whose pages have screenshots.
 */
function ExportPanel({ run, page, pages, selected, onToggle, t }) {
  const [blur, setBlur] = useState("entities");
  const [boxes, setBoxes] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const entityCount = pages.reduce((n, p) => n + p.entities.length, 0);
  const selectedCount = selected.size;

  async function download(format) {
    setBusy(true);
    setError(null);
    try {
      const body = { format, blur, boxes };
      if (format === "png") body.page_numbers = [page.number];
      if (selectedCount > 0 && selectedCount < entityCount)
        body.entity_ids = [...selected];
      const url = await renderRunDocument(run.id, body);
      const a = document.createElement("a");
      a.href = url;
      a.download = "";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border bg-background/40 px-3 py-2 text-sm">
      <span className="font-medium">{t("run.doc.export")}</span>
      <label className="flex items-center gap-1.5">
        {t("run.doc.blur")}
        <select
          value={blur}
          onChange={(e) => setBlur(e.target.value)}
          className="rounded-md border border-border bg-background px-1.5 py-0.5"
        >
          <option value="entities">{t("run.doc.blur.entities")}</option>
          <option value="full">{t("run.doc.blur.full")}</option>
          <option value="none">{t("run.doc.blur.none")}</option>
        </select>
      </label>
      <label className="flex items-center gap-1.5">
        <input
          type="checkbox"
          checked={boxes}
          onChange={(e) => setBoxes(e.target.checked)}
        />
        {t("run.doc.boxes")}
      </label>
      <span className="text-xs text-muted-foreground">
        {selectedCount > 0
          ? t("run.doc.selected").replace("{n}", selectedCount)
          : t("run.doc.allEntities")}
      </span>
      <div className="ml-auto flex items-center gap-2">
        {busy && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
        {error && (
          <span className="max-w-48 truncate text-xs text-destructive" title={error}>
            {error}
          </span>
        )}
        <Button size="sm" variant="outline" disabled={busy} onClick={() => download("png")}>
          <FileImage className="h-4 w-4" />
          {t("run.doc.png")}
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => download("zip")}>
          <Download className="h-4 w-4" />
          {t("run.doc.zip")}
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => download("pdf")}>
          <FileText className="h-4 w-4" />
          {t("run.doc.pdf")}
        </Button>
      </div>
    </div>
  );
}

/**
 * The analysed document, page by page: the screenshot with the boxes of what
 * was found (files), the text with the spans marked, the safety verdict and
 * the classification of the page. Hovering a highlight, in the image, the text
 * or the list, lights it up everywhere.
 */
export default function RunDocument({ run, source }) {
  const { t } = useI18n();
  const pages = useMemo(() => buildPages(run, source), [run, source]);
  const [index, setIndex] = useState(0);
  const [layers, setLayers] = useState({ entities: true, relations: true });
  // A run that asks to anonymize hides the text for good; otherwise it is
  // clear, and the checkbox hides it on screen.
  const anonymizing = isAnonymizing(run);
  const [maskedByUser, setMasked] = useState(false);
  const masked = anonymizing || maskedByUser;
  const [activeId, setActiveId] = useState(null);
  // The entities to blur on export, as "page:entity" ids (entity ids restart
  // on every page). Empty means every entity.
  const [selected, setSelected] = useState(new Set());
  // The boxes users drew, kept in the database: blurred on export.
  const { boxes: drawn, add: addDrawn, remove: removeDrawn } = usePageBboxes(run?.id);
  const [drawMode, setDrawMode] = useState(false);

  // A new run starts on its first page, with nothing selected.
  const runId = run?.id;
  useEffect(() => {
    setIndex(0);
    setSelected(new Set());
    setDrawMode(false);
  }, [runId]);

  const toggleEntity = (id) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const page = pages[Math.min(index, pages.length - 1)];
  const items = useMemo(
    () => (page ? highlights(page, layers, masked) : []),
    [page, layers, masked]
  );
  if (!page) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-3">
          <CardTitle>{t("run.doc.title")}</CardTitle>
          <div className="ml-auto flex items-center gap-2">
            <Button
              size="icon"
              variant="outline"
              disabled={index === 0}
              onClick={() => setIndex(index - 1)}
              aria-label="←"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm tabular-nums">
              {t("run.page")} {index + 1} / {pages.length}
            </span>
            <Button
              size="icon"
              variant="outline"
              disabled={index >= pages.length - 1}
              onClick={() => setIndex(index + 1)}
              aria-label="→"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <CardDescription className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {[
            ["entities", "run.step.ner"],
            ["relations", "run.step.relation"],
          ].map(([layer, key]) => (
            <label key={layer} className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={layers[layer]}
                onChange={(e) => setLayers({ ...layers, [layer]: e.target.checked })}
              />
              {t(key)}
            </label>
          ))}
          <label className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={masked}
              disabled={anonymizing}
              onChange={(e) => setMasked(e.target.checked)}
            />
            {t("run.doc.mask")}
          </label>
          {page.filename && <span>· {page.filename}</span>}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {pages.some((p) => p.image) && (
          <ExportPanel
            run={run}
            page={page}
            pages={pages}
            selected={selected}
            onToggle={toggleEntity}
            t={t}
          />
        )}
        <div className="flex flex-wrap items-center gap-2">
          {page.unsafe && (
            <Badge variant="destructive" className="gap-1">
              <AlertTriangle className="h-3 w-3" />
              {t("run.unsafe")}
            </Badge>
          )}
          {page.safety
            .flatMap((check) => check.labels.map((l) => ({ ...l, check: check.name })))
            .sort((a, b) => Number(b.flagged) - Number(a.flagged))
            .map((l) => (
              <Badge
                key={`${l.check}-${l.label}`}
                variant={l.flagged ? "destructive" : "muted"}
                title={l.check}
              >
                {l.label} <span className="ml-1 tabular-nums opacity-70">{pct(l.score)}</span>
              </Badge>
            ))}
          {page.imageClassifications.flatMap((c) =>
            c.labels.map((label) => (
              <Badge key={`img-${c.name}-${label}`} title={`${t("run.doc.image")} · ${c.name}`}>
                {t("run.doc.image")}: {c.name}: {label}
                <span className="ml-1 tabular-nums opacity-70">{pct(c.scores?.[label])}</span>
              </Badge>
            ))
          )}
          {page.classifications.flatMap((c) =>
            c.labels.length ? (
              c.labels.map((label) => (
                <Badge key={`${c.name}-${label}`} variant="muted" title={c.name}>
                  {c.name}: {label}
                  <span className="ml-1 tabular-nums opacity-70">{pct(c.scores?.[label])}</span>
                </Badge>
              ))
            ) : (
              <Badge key={c.name} variant="muted">
                {c.name}: {t("run.noLabel")}
              </Badge>
            )
          )}
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="space-y-3">
            {page.image && (
              <>
                <label className="flex items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={drawMode}
                    onChange={(e) => setDrawMode(e.target.checked)}
                  />
                  <PencilRuler className="h-4 w-4" />
                  {t("run.doc.draw")}
                  <span className="text-xs text-muted-foreground">
                    · {t("run.doc.drawn").replace("{n}", drawn.filter((b) => b.page_number === page.number).length)}
                  </span>
                </label>
                <PageImage
                  page={page}
                  items={items}
                  activeId={activeId}
                  onActive={setActiveId}
                  drawn={drawn.filter((b) => b.page_number === page.number)}
                  drawMode={drawMode}
                  onDraw={(box) => addDrawn(page.number, box)}
                  onDeleteDrawn={removeDrawn}
                />
              </>
            )}
            {page.anonymized !== null ? (
              <AnonymizedText content={page.anonymized} t={t} />
            ) : (
              <PageText
              page={page}
              items={items}
              activeId={activeId}
              onActive={setActiveId}
              masked={masked}
              />
            )}
          </div>
          <Side
            page={page}
            activeId={activeId}
            onActive={setActiveId}
            layers={layers}
            masked={masked}
            selected={selected}
            onToggle={toggleEntity}
            t={t}
          />
        </div>
      </CardContent>
    </Card>
  );
}
