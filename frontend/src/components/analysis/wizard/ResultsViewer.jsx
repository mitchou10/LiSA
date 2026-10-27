import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  EyeOff,
  FileImage,
  FileText,
  Loader2,
  PencilRuler,
} from "lucide-react";
import { Button } from "../../ui/button";
import { Badge } from "../../ui/badge";
import { useEntityLabels } from "../../../hooks/useEntityLabels";
import { usePageBboxes } from "../../../hooks/usePageBboxes";
import { renderRunDocument } from "../../../lib/api";
import { buildPages, colorFor, isAnonymizing } from "../../../lib/runModel";
import { cn } from "../../../lib/utils";
import { useI18n } from "../../../lib/i18n.jsx";
import DrawBoxDialog from "../DrawBoxDialog";
import { AnonymizedText, PageImage, PageText, highlights } from "../RunDocument";

const pct = (n) => (n == null ? "" : `${Math.round(n * 100)}%`);
const mask = (text) => text.replace(/\S/g, "*");
const LAYERS = { entities: true, relations: false };

const key = (page, entity) => `${page.number}:${entity.id}`;

/** What to blur and how to download it. Only for runs that have page images. */
function ExportBar({ run, page, total, checked, t }) {
  const [blur, setBlur] = useState("entities");
  const [boxes, setBoxes] = useState(false);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  const nothing = blur === "entities" && checked.size === 0;

  async function download(format) {
    setBusy(format);
    setError(null);
    try {
      const body = { format, blur: nothing ? "none" : blur, boxes };
      if (format === "png") body.page_numbers = [page.number];
      if (blur === "entities" && checked.size > 0 && checked.size < total)
        body.entity_ids = [...checked];
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
      setBusy(null);
    }
  }

  const formats = [
    ["png", FileImage, t("wiz.export.png"), t("wiz.export.png.hint")],
    ["zip", Download, t("wiz.export.zip"), t("wiz.export.zip.hint")],
    ["pdf", FileText, t("wiz.export.pdf"), t("wiz.export.pdf.hint")],
  ];

  return (
    <section className="space-y-4 rounded-xl border border-border bg-background/40 p-4">
      <div>
        <h3 className="font-medium">{t("wiz.export.title")}</h3>
        <p className="text-sm text-muted-foreground">{t("wiz.export.desc")}</p>
      </div>

      <div className="space-y-1.5">
        <div className="text-sm font-medium">{t("wiz.export.blur")}</div>
        <div className="inline-flex flex-wrap rounded-lg bg-muted p-1" role="radiogroup">
          {[
            ["entities", t("wiz.export.blur.entities").replace("{n}", checked.size)],
            ["full", t("wiz.export.blur.full")],
            ["none", t("wiz.export.blur.none")],
          ].map(([value, label]) => (
            <button
              type="button"
              key={value}
              role="radio"
              aria-checked={blur === value}
              onClick={() => setBlur(value)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                blur === value ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </button>
          ))}
        </div>
        {nothing && <p className="text-xs text-muted-foreground">{t("wiz.export.nothing")}</p>}
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        {formats.map(([format, Icon, label, hint]) => (
          <Button
            key={format}
            variant="outline"
            disabled={!!busy}
            onClick={() => download(format)}
            className="h-auto flex-col items-start gap-0.5 px-3 py-2.5 text-left"
          >
            <span className="flex items-center gap-2">
              {busy === format ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" />}
              {label}
            </span>
            <span className="text-xs font-normal text-muted-foreground">{hint}</span>
          </Button>
        ))}
      </div>

      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        <input type="checkbox" checked={boxes} onChange={(e) => setBoxes(e.target.checked)} />
        {t("run.doc.boxes")}
      </label>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </section>
  );
}

/**
 * The analysed document next to what was found. Every entity is ticked by
 * default: ticked means "hide it" on export. Nothing to learn, nothing to set
 * up: untick what should stay readable, then download or leave.
 */
export default function ResultsViewer({ run, source }) {
  const { t } = useI18n();
  const pages = useMemo(() => buildPages(run, source), [run, source]);
  const [index, setIndex] = useState(0);
  const [view, setView] = useState("image");
  const [activeId, setActiveId] = useState(null);
  // Boxes drawn by hand on the page: blurred on export, kept for the metrics.
  const { boxes: drawn, add: addDrawn, remove: removeDrawn } = usePageBboxes(run?.id);
  const [drawMode, setDrawMode] = useState(false);
  // A box just drawn, waiting for its label: { pageNumber, box, url }.
  const [pending, setPending] = useState(null);
  const anonymizing = isAnonymizing(run);
  const [maskedByUser, setMasked] = useState(false);
  const masked = anonymizing || maskedByUser;

  // Every entity starts ticked ("page:entity", ids restart on every page).
  const allKeys = useMemo(() => pages.flatMap((p) => p.entities.map((e) => key(p, e))), [pages]);
  const [checked, setChecked] = useState(() => new Set(allKeys));
  useEffect(() => setChecked(new Set(allKeys)), [allKeys.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps

  const labels = useEntityLabels(run, pages);
  const page = pages[Math.min(index, pages.length - 1)];
  const items = useMemo(() => (page ? highlights(page, LAYERS, masked) : []), [page, masked]);
  if (!page) return null;

  const hasImages = pages.some((p) => p.image);
  const showImage = !!page.image && view === "image";
  const pageKeys = page.entities.map((e) => key(page, e));
  const alerts = page.safety.flatMap((c) => c.labels.filter((l) => l.flagged).map((l) => ({ ...l, check: c.name })));
  const tags = [
    ...page.classifications.flatMap((c) => c.labels.map((l) => `${c.name}: ${l}`)),
    ...page.imageClassifications.flatMap((c) => c.labels.map((l) => `${t("run.doc.image")}: ${l}`)),
  ];

  const toggle = (k) =>
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  const setPage = (on) =>
    setChecked((prev) => {
      const next = new Set(prev);
      for (const k of pageKeys) (on ? next.add(k) : next.delete(k));
      return next;
    });

  return (
    <div className="space-y-5">
      {alerts.length > 0 && (
        <div className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
          <div>
            <div className="font-medium text-destructive">{t("wiz.viewer.alert")}</div>
            <div className="text-muted-foreground">
              {alerts.map((a) => `${a.check}: ${a.label} ${pct(a.score)}`).join(" · ")}
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {pages.length > 1 && (
              <>
                <Button size="icon" variant="outline" disabled={index === 0} onClick={() => setIndex(index - 1)} aria-label="←">
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm tabular-nums">
                  {t("run.page")} {index + 1} / {pages.length}
                </span>
                <Button size="icon" variant="outline" disabled={index >= pages.length - 1} onClick={() => setIndex(index + 1)} aria-label="→">
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </>
            )}
            <div className="ml-auto flex items-center gap-2">
              {page.image && (
                <div className="inline-flex rounded-lg bg-muted p-0.5 text-sm">
                  {[
                    ["image", t("wiz.viewer.image")],
                    ["text", t("wiz.viewer.text")],
                  ].map(([v, label]) => (
                    <button
                      type="button"
                      key={v}
                      onClick={() => setView(v)}
                      className={cn(
                        "rounded-md px-2.5 py-1 font-medium",
                        view === v ? "bg-background shadow-sm" : "text-muted-foreground"
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
              {showImage && (
                <Button
                  size="sm"
                  variant={drawMode ? "secondary" : "ghost"}
                  onClick={() => setDrawMode(!drawMode)}
                  title={t("run.doc.drawHint")}
                >
                  <PencilRuler className="h-4 w-4" />
                  {t("run.doc.draw")}
                </Button>
              )}
              {!anonymizing && (
                <Button size="sm" variant="ghost" onClick={() => setMasked(!maskedByUser)}>
                  {masked ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                  {masked ? t("wiz.viewer.show") : t("wiz.viewer.hide")}
                </Button>
              )}
            </div>
          </div>

          {showImage ? (
            <PageImage
              page={page}
              items={items}
              activeId={activeId}
              onActive={setActiveId}
              drawn={drawn.filter((b) => b.page_number === page.number)}
              drawMode={drawMode}
              onDraw={(box, url) => setPending({ pageNumber: page.number, box, url })}
              onDeleteDrawn={removeDrawn}
            />
          ) : page.anonymized !== null ? (
            <AnonymizedText content={page.anonymized} t={t} />
          ) : (
            <PageText page={page} items={items} activeId={activeId} onActive={setActiveId} masked={masked} />
          )}

          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {tags.map((tag) => (
                <Badge key={tag} variant="muted">
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </div>

        <aside className="space-y-3">
          <div className="flex items-center gap-2">
            <h3 className="font-medium">{t("wiz.viewer.found")}</h3>
            <span className="text-xs text-muted-foreground">{page.entities.length}</span>
            {page.entities.length > 0 && hasImages && (
              <span className="ml-auto flex gap-3 text-xs">
                <button type="button" className="text-primary hover:underline" onClick={() => setPage(true)}>
                  {t("run.all")}
                </button>
                <button type="button" className="text-primary hover:underline" onClick={() => setPage(false)}>
                  {t("run.none")}
                </button>
              </span>
            )}
          </div>
          {hasImages && page.entities.length > 0 && (
            <p className="text-xs text-muted-foreground">{t("wiz.viewer.hint")}</p>
          )}
          {page.entities.length === 0 && <p className="text-sm text-muted-foreground">{t("run.nothing")}</p>}
          <ul className="space-y-1">
            {page.entities.map((e) => {
              const k = key(page, e);
              return (
                <li
                  key={e.id}
                  onMouseEnter={() => setActiveId(e.id)}
                  onMouseLeave={() => setActiveId(null)}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border border-transparent px-2 py-1.5 text-sm",
                    activeId === e.id && "border-border bg-muted"
                  )}
                >
                  {hasImages && (
                    <input
                      type="checkbox"
                      checked={checked.has(k)}
                      onChange={() => toggle(k)}
                      aria-label={t("run.doc.selectEntity")}
                    />
                  )}
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: colorFor(e.category) }} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{masked ? mask(e.text) : e.text}</span>
                    <span className="block text-xs text-muted-foreground">{e.label}</span>
                  </span>
                  <Badge variant={e.action === "block" ? "destructive" : "muted"}>
                    {t(`sensitive.action.${e.action}`)}
                  </Badge>
                </li>
              );
            })}
          </ul>
          {hasImages && pages.length > 1 && (
            <p className="text-xs text-muted-foreground">
              {t("wiz.viewer.total").replace("{n}", checked.size).replace("{total}", allKeys.length)}
            </p>
          )}
        </aside>
      </div>

      {hasImages ? (
        <ExportBar run={run} page={page} total={allKeys.length} checked={checked} t={t} />
      ) : (
        <p className="rounded-lg border border-dashed border-border p-3 text-sm text-muted-foreground">
          {t("wiz.results.exportText")}
        </p>
      )}

      <DrawBoxDialog
        pending={pending}
        labels={labels}
        onCancel={() => setPending(null)}
        onSave={(label) => {
          addDrawn(pending.pageNumber, { ...pending.box, label });
          setPending(null);
        }}
      />
    </div>
  );
}
