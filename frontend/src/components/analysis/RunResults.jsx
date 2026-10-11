import { AlertTriangle, CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { Badge } from "../ui/badge";
import { formatDuration } from "../../lib/runModel";
import { cn } from "../../lib/utils";
import { useI18n } from "../../lib/i18n.jsx";

const SEVERITY_VARIANT = { low: "muted", medium: "default", high: "destructive" };

const STATUS_ICON = {
  pending: { Icon: Circle, className: "text-muted-foreground" },
  running: { Icon: Loader2, className: "text-primary animate-spin" },
  success: { Icon: CheckCircle2, className: "text-success" },
  error: { Icon: XCircle, className: "text-destructive" },
  revoked: { Icon: XCircle, className: "text-muted-foreground" },
};

const pct = (n) => (n == null ? "" : `${Math.round(n * 100)}%`);

function PageTitle({ page, t }) {
  return (
    <div className="mb-1.5 text-xs font-medium text-muted-foreground">
      {t("run.page")} {page.page_number ?? 1}
    </div>
  );
}

function Empty({ t }) {
  return <p className="text-sm text-muted-foreground">{t("run.nothing")}</p>;
}

function ParserResult({ output, t }) {
  const pages = output?.pages ?? [];
  return (
    <p className="text-sm">
      {pages.length} {t("run.pagesParsed")}
    </p>
  );
}

function NerResult({ output, t }) {
  const pages = output?.pages ?? [];
  if (!pages.some((p) => p.entities.length)) return <Empty t={t} />;
  return pages.map((page, i) => (
    <div key={i}>
      <PageTitle page={page} t={t} />
      <div className="flex flex-wrap gap-1.5">
        {page.entities.map((e) => (
          <Badge
            key={e.id}
            variant={e.flagged ? SEVERITY_VARIANT[e.severity] : "muted"}
            title={`${e.label} · ${e.action} · ${pct(e.score)}`}
          >
            {e.text}
            <span className="ml-1.5 opacity-70">{e.label}</span>
            <span className="ml-1.5 tabular-nums opacity-70">{pct(e.score)}</span>
          </Badge>
        ))}
      </div>
    </div>
  ));
}

function RelationResult({ output, t }) {
  const pages = output?.pages ?? [];
  if (!pages.some((p) => p.relations.length)) return <Empty t={t} />;
  return pages.map((page, i) => (
    <div key={i}>
      <PageTitle page={page} t={t} />
      <ul className="space-y-1 text-sm">
        {page.relations.map((r) => (
          <li key={r.id} className="flex flex-wrap items-center gap-1.5">
            <Badge variant="muted">{r.head.text}</Badge>
            <span className="text-xs text-muted-foreground">— {r.relation} →</span>
            <Badge variant="muted">{r.tail.text}</Badge>
            <span className="text-xs text-muted-foreground">{pct(r.score)}</span>
          </li>
        ))}
      </ul>
    </div>
  ));
}

function ClassificationResult({ output, t }) {
  const pages = output?.pages ?? [];
  return pages.map((page, i) => (
    <div key={i}>
      <PageTitle page={page} t={t} />
      <ul className="space-y-1 text-sm">
        {page.classifications.map((c) => (
          <li key={c.name} className="flex flex-wrap items-center gap-1.5">
            <span className="font-medium">{c.name}</span>
            {c.labels.length ? (
              c.labels.map((l) => (
                <Badge key={l}>
                  {l}
                  {c.scores?.[l] != null && (
                    <span className="ml-1.5 tabular-nums opacity-70">{pct(c.scores[l])}</span>
                  )}
                </Badge>
              ))
            ) : (
              <span className="text-xs text-muted-foreground">{t("run.noLabel")}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  ));
}

function SafetyResult({ output, t }) {
  const pages = output?.pages ?? [];
  return (
    <>
      <div
        className={cn(
          "flex items-center gap-2 text-sm font-medium",
          output?.unsafe ? "text-destructive" : "text-success"
        )}
      >
        {output?.unsafe ? (
          <AlertTriangle className="h-4 w-4" />
        ) : (
          <CheckCircle2 className="h-4 w-4" />
        )}
        {output?.unsafe ? t("run.unsafe") : t("run.safe")}
      </div>
      {pages.map((page, i) => (
        <div key={i}>
          <PageTitle page={page} t={t} />
          <ul className="space-y-1 text-sm">
            {page.safety.map((check) => (
              <li key={check.name} className="flex flex-wrap items-center gap-1.5">
                <span className="font-medium">{check.name}</span>
                {check.labels.map((l) => (
                  <Badge key={l.label} variant={l.flagged ? "destructive" : "success"}>
                    {l.label}
                    {l.score != null && (
                      <span className="ml-1.5 opacity-70">{pct(l.score)}</span>
                    )}
                  </Badge>
                ))}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </>
  );
}

function ImageClassificationResult({ output, t }) {
  const images = output?.images ?? [];
  return images.map((image, i) => (
    <div key={i}>
      <div className="mb-1.5 text-xs font-medium text-muted-foreground">
        {image.page_number != null ? `${t("run.page")} ${image.page_number}` : image.s3_key}
      </div>
      <ul className="space-y-1 text-sm">
        {image.classifications.map((c) => (
          <li key={c.name} className="flex flex-wrap items-center gap-1.5">
            <span className="font-medium">{c.name}</span>
            {c.labels.length ? (
              c.labels.map((l) => (
                <Badge key={l}>
                  {l}
                  <span className="ml-1.5 tabular-nums opacity-70">{pct(c.scores?.[l])}</span>
                </Badge>
              ))
            ) : (
              <span className="text-xs text-muted-foreground">{t("run.noLabel")}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  ));
}

function AnonymizeResult({ output, t }) {
  const pages = output?.pages ?? [];
  return (
    <p className="text-sm">
      {pages.length} {t("run.pagesAnonymized")}
    </p>
  );
}

const RESULT = {
  image_classification: ImageClassificationResult,
  anonymize: AnonymizeResult,
  parser: ParserResult,
  ner: NerResult,
  relation: RelationResult,
  classification: ClassificationResult,
  safety: SafetyResult,
};

function Step({ step, t }) {
  const status = step.waiting && step.status === "pending" ? "pending" : step.status;
  const meta = STATUS_ICON[status] ?? STATUS_ICON.pending;
  const { Icon } = meta;
  const Result = RESULT[step.step];
  return (
    <div className="space-y-2 rounded-lg border border-border bg-background/40 p-3">
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4 shrink-0", meta.className)} />
        <span className="flex-1 text-sm font-medium">{t(`run.step.${step.step}`)}</span>
        {step.waiting && status === "pending" && (
          <span className="text-xs text-muted-foreground">{t("run.waiting")}</span>
        )}
        {step.duration != null && (
          <span
            className="text-xs tabular-nums text-muted-foreground"
            title={t("run.duration.hint")}
          >
            {formatDuration(step.duration)}
          </span>
        )}
        <Badge variant={status === "error" ? "destructive" : "muted"}>
          {t(`status.${status}`)}
        </Badge>
      </div>
      {status === "running" && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${step.progress ?? 0}%` }}
          />
        </div>
      )}
      {step.error && <p className="text-xs text-destructive">{step.error}</p>}
      {status === "success" && Result && <Result output={step.output} t={t} />}
    </div>
  );
}

/** The steps of a run, in order, each with its result once it is done. */
export default function RunResults({ run }) {
  const { t } = useI18n();
  if (!run) return null;
  return (
    <div className="space-y-3">
      {run.duration != null && (
        <p className="text-sm text-muted-foreground" title={t("run.duration.hint")}>
          {t("run.duration.total")}:{" "}
          <span className="font-medium tabular-nums text-foreground">
            {formatDuration(run.duration)}
          </span>
        </p>
      )}
      {run.steps.map((step) => (
        <Step key={step.task_id} step={step} t={t} />
      ))}
    </div>
  );
}
