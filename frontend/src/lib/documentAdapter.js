// Turn analyser output + OCR pages into the DocumentResultView format.
//
// The parser service gives, per page, an image, its size and word boxes with
// character offsets into the page text. Analysers report entities as
// start_char/end_char in that same text, so an entity maps to the words whose
// offsets overlap it.

const TYPE_COLORS = {
  PII: "#8b5cf6",
  POLICE: "#ef4444",
  HEALTH: "#10b981",
  LEGAL: "#3b82f6",
  SECRET: "#f59e0b",
};
const SEVERITY_COLORS = { high: "#ef4444", medium: "#f59e0b", low: "#3b82f6" };

function colorFor(entity, severity) {
  const type = String(entity.type || "").toUpperCase();
  if (TYPE_COLORS[type]) return TYPE_COLORS[type];
  if (type.includes("SECRET") || type.includes("KEY")) return TYPE_COLORS.SECRET;
  return SEVERITY_COLORS[severity] || SEVERITY_COLORS.medium;
}

// Group consecutive words that sit on the same visual line.
function groupByLine(words) {
  const lines = [];
  for (const w of words) {
    const last = lines.at(-1);
    const ref = last?.at(-1);
    if (ref && Math.abs(w.y - ref.y) < Math.max(ref.height, w.height) * 0.5) {
      last.push(w);
    } else {
      lines.push([w]);
    }
  }
  return lines;
}

function unionBox(words) {
  const x1 = Math.min(...words.map((w) => w.x));
  const y1 = Math.min(...words.map((w) => w.y));
  const x2 = Math.max(...words.map((w) => w.x + w.width));
  const y2 = Math.max(...words.map((w) => w.y + w.height));
  return { x: x1, y: y1, width: x2 - x1, height: y2 - y1 };
}

/** Boxes (one per visual line) covering the character range [start, end). */
export function boxesForRange(words, start, end) {
  const hit = words.filter((w) => w.start < end && w.end > start);
  return groupByLine(hit).map(unionBox);
}

/**
 * @param {object} result   consolidated backend result ({ pages: [{page_number, detections}] })
 * @param {Array}  docPages pages sent for analysis, in order:
 *   { page_number, filename, width, height, image, words } (image/words are
 *   absent for plain text files).
 */
export function adaptToDocumentResult(result, docPages) {
  const byNumber = new Map((result?.pages || []).map((p) => [p.page_number, p]));

  const pages = docPages.map((doc, pageIndex) => {
    const detections = byNumber.get(doc.page_number)?.detections || [];
    const bboxes = [];
    const classifications = [];

    for (const det of detections) {
      const entities = det.entities || [];
      for (const entity of entities) {
        if (entity.flagged === false) continue;
        if (entity.start_char == null || entity.start_char < 0) continue;
        const severity = entity.severity || det.severity || "medium";
        const color = colorFor(entity, severity);
        const boxes = boxesForRange(doc.words || [], entity.start_char, entity.end_char);
        boxes.forEach((box, i) => {
          bboxes.push({
            id: `bbox-${pageIndex}-${bboxes.length}`,
            ...box,
            classification: entity.label || entity.type || "entity",
            color,
            description: `${det.service || "service"} · ${entity.type || ""} · « ${entity.text || ""} »`,
            probability: entity.confidence ?? det.confidence ?? 0,
            severity,
            proposals: [],
            decision: null,
            service: det.service,
            part: i,
          });
        });
      }
      // Whole-text verdicts (prompt injection, toxicity, …) become page tags.
      if (det.flagged && entities.length === 0) {
        classifications.push({
          label: det.classification || det.service || "flagged",
          probability: det.confidence ?? 0,
        });
      }
    }

    classifications.sort((a, b) => b.probability - a.probability);
    return {
      page_number: doc.page_number,
      filename: doc.filename,
      width: doc.width || 612,
      height: doc.height || 792,
      image: doc.image || null,
      classifications,
      bboxes,
    };
  });

  return { kind: "document", pages, metadata: { source: "web", ocr: true } };
}
