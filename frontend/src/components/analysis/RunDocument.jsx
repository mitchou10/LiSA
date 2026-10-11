import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ChevronLeft, ChevronRight, ImageOff, Loader2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { usePageImage } from "../../hooks/usePageImage";
import { buildPages, colorFor, isAnonymizing, segments } from "../../lib/runModel";
import { cn } from "../../lib/utils";
import { useI18n } from "../../lib/i18n.jsx";

const HEAD_COLOR = "hsl(215 80% 50%)";
const TAIL_COLOR = "hsl(285 70% 50%)";
const pct = (n) => (n == null ? "" : `${Math.round(n * 100)}%`);

// Hide a text: every character but whitespace becomes "*", so lengths and
// offsets are unchanged and the shape of the text stays recognisable.
const mask = (text) => text.replace(/\S/g, "*");
const show = (text, masked) => (masked ? mask(text) : text);

// Every highlight of a page, as one list: what to draw, where, in what colour.
function highlights(page, layers, masked) {
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
function PageImage({ page, items, activeId, onActive }) {
  const { t } = useI18n();
  const { url, error, loading } = usePageImage(page.image);

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
    <div className="relative overflow-hidden rounded-lg border border-border">
      <img src={url} alt={`${t("run.page")} ${page.number}`} className="block w-full" />
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
  );
}

/** The text the anonymize worker returned: stars, with a coloured [LABEL] per entity. */
function AnonymizedText({ content, t }) {
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
function PageText({ page, items, activeId, onActive, masked }) {
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

function Side({ page, activeId, onActive, layers, masked, t }) {
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

  // A new run starts on its first page.
  const runId = run?.id;
  useEffect(() => setIndex(0), [runId]);

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
              <PageImage page={page} items={items} activeId={activeId} onActive={setActiveId} />
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
            t={t}
          />
        </div>
      </CardContent>
    </Card>
  );
}
