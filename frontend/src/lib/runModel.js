// Turns a finished run into what the document view draws: pages, and for each
// page the entities and relations to put on it.

// Same rule as the backend: a form feed starts a new page.
export function textToPages(text) {
  const parts = text.split("\f").filter((p) => p.trim());
  return (parts.length ? parts : [text]).map((content, i) => ({
    number: i + 1,
    content,
  }));
}

const done = (steps, name) =>
  steps.find((s) => s.step === name && s.status === "success");

const byPage = (step, key) => {
  const map = new Map();
  for (const page of step?.output?.pages ?? []) map.set(page.page_number, page[key] ?? []);
  return map;
};

/**
 * pages: [{ number, content, image: {taskId, number}|null,
 *           entities, relations, safety, classifications }]
 * `source` is what was sent: text pages are rebuilt locally, file pages come
 * from the parser (text, and a screenshot to put the boxes on).
 */
export function buildPages(run, source) {
  if (!run) return [];
  const parser = done(run.steps, "parser");
  const entities = byPage(done(run.steps, "ner"), "entities");
  const relations = byPage(done(run.steps, "relation"), "relations");
  const safety = byPage(done(run.steps, "safety"), "safety");
  const classes = byPage(done(run.steps, "classification"), "classifications");
  // What the anonymize worker returned: stars, with a [LABEL] marker per entity.
  const anonymized = new Map(
    (done(run.steps, "anonymize")?.output?.pages ?? []).map((p) => [p.page_number, p.content])
  );
  const unsafe = new Map(
    (done(run.steps, "safety")?.output?.pages ?? []).map((p) => [p.page_number, p.unsafe])
  );

  const base = parser
    ? (parser.output?.pages ?? []).map((p) => ({
        number: p.page_number,
        content: p.content ?? "",
        image: p.s3_key ? { taskId: parser.task_id, number: p.page_number } : null,
        filename: p.filename,
      }))
    : (source?.pages ?? []).map((p) => ({ ...p, image: null }));

  return base.map((page) => ({
    ...page,
    entities: entities.get(page.number) ?? [],
    relations: relations.get(page.number) ?? [],
    safety: safety.get(page.number) ?? [],
    unsafe: unsafe.get(page.number) ?? false,
    classifications: classes.get(page.number) ?? [],
    anonymized: anonymized.get(page.number) ?? null,
  }));
}

// Stable colour per name (a category, a relation): same name, same colour.
export const isAnonymizing = (run) => !!run?.steps.some((s) => s.step === "anonymize");

export function colorFor(name) {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${hash} 70% 45%)`;
}

/**
 * Cut `content` at every span boundary: each segment knows which spans cover
 * it, so overlapping spans (an entity inside a relation end) both show.
 */
export function segments(content, spans) {
  const clamp = (n) => Math.max(0, Math.min(content.length, n));
  const cuts = new Set([0, content.length]);
  for (const s of spans) {
    cuts.add(clamp(s.start));
    cuts.add(clamp(s.end));
  }
  const points = [...cuts].sort((a, b) => a - b);
  return points.slice(0, -1).map((start, i) => {
    const end = points[i + 1];
    return {
      start,
      end,
      text: content.slice(start, end),
      spans: spans.filter((s) => s.start <= start && s.end >= end),
    };
  });
}
