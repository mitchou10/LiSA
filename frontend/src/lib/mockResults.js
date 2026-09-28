// Mock result generators for text and document analysis.
// These define the data model used by the dedicated result views
// (TextResultView, DocumentResultView).

// ── Text analysis ──────────────────────────────────────────────────────────

const TEXT_PATTERNS = [
  {
    re: /ignore (?:all(?:\s+previous)?|previous|the above)\s+instructions?/gi,
    classification: "prompt_injection",
    label: "Prompt Injection",
    description: "Tente d'outrepasser les instructions système en demandant d'ignorer les règles précédentes.",
    severity: "high",
    proposals: [
      { label: "Jailbreak", probability: 0.58 },
      { label: "Légitime", probability: 0.08 },
    ],
  },
  {
    re: /\bDAN\b/g,
    classification: "jailbreak",
    label: "Jailbreak",
    description: "Référence au prompt « Do Anything Now », une technique classique de contournement de sécurité.",
    severity: "high",
    proposals: [
      { label: "Prompt Injection", probability: 0.61 },
      { label: "Légitime", probability: 0.05 },
    ],
  },
  {
    re: /sk-[a-zA-Z0-9]{10,}/g,
    classification: "secret_leak",
    label: "Fuite de secret",
    description: "Clé API (format OpenAI) détectée en clair dans le texte.",
    severity: "high",
    proposals: [
      { label: "Donnée sensible", probability: 0.72 },
      { label: "Légitime", probability: 0.03 },
    ],
  },
  {
    re: /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+/g,
    classification: "pii",
    label: "Donnée personnelle (PII)",
    description: "Adresse e-mail détectée — potentiellement une donnée personnelle (RGPD).",
    severity: "medium",
    proposals: [
      { label: "Légitime", probability: 0.45 },
      { label: "Donnée sensible", probability: 0.30 },
    ],
  },
  {
    re: /\b(kill|destroy|hate|idiot|stupid)\b/gi,
    classification: "toxicity",
    label: "Toxicité",
    description: "Langage potentiellement toxique ou agressif détecté.",
    severity: "medium",
    proposals: [
      { label: "Légitime", probability: 0.35 },
      { label: "Insulte", probability: 0.55 },
    ],
  },
  {
    re: /\bFR\d{2}(?:\s?\d{4}){5}\s?\d{3}\b/g,
    classification: "pii",
    label: "Donnée personnelle (PII)",
    description: "Numéro IBAN détecté — donnée financière sensible (RGPD).",
    severity: "high",
    proposals: [
      { label: "Donnée sensible", probability: 0.85 },
      { label: "Légitime", probability: 0.05 },
    ],
  },
];

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Generate a text analysis result with character-span annotations.
 * Each span carries: classification, label, description, probability,
 * severity, and a list of alternative proposals with probabilities.
 */
export async function mockTextAnalysis(text) {
  await delay(400 + Math.random() * 400);

  const spans = [];
  let spanId = 0;

  for (const { re, classification, label, description, severity, proposals } of TEXT_PATTERNS) {
    for (const match of text.matchAll(re)) {
      const start = match.index;
      const end = start + match[0].length;
      // Skip overlaps with existing spans
      if (spans.some((s) => start < s.end_char && end > s.start_char)) continue;

      const baseProb = 0.6 + Math.random() * 0.35;
      spans.push({
        id: `span-${spanId++}`,
        start_char: start,
        end_char: end,
        text: match[0],
        classification,
        label,
        description,
        probability: Number(baseProb.toFixed(3)),
        severity,
        proposals: proposals.map((p) => ({
          ...p,
          probability: Number(p.probability.toFixed(3)),
        })),
        decision: null, // "validated" | "rejected" | null
      });
    }
  }

  return {
    kind: "text",
    text,
    spans,
    metadata: { mock: true, source: "web" },
  };
}

// ── Document analysis ──────────────────────────────────────────────────────

const DOC_CLASSIFICATIONS = [
  "Facture",
  "Contrat",
  "Relevé bancaire",
  "Pièce d'identité",
  "Courrier",
  "Tableau",
  "Rapport",
  "Formulaire",
];

const BBOX_CLASSIFICATIONS = [
  { label: "Titre", color: "#3b82f6" },
  { label: "Paragraphe", color: "#10b981" },
  { label: "Tableau", color: "#f59e0b" },
  { label: "Signature", color: "#ef4444" },
  { label: "Montant", color: "#8b5cf6" },
  { label: "Date", color: "#06b6d4" },
  { label: "Adresse", color: "#ec4899" },
  { label: "Logo", color: "#6b7280" },
];

/** Labels available for manual text annotation (mirrors BBOX_LABELS). */
export const TEXT_LABELS = [
  { label: "Prompt Injection", color: "#ef4444", severity: "high" },
  { label: "Jailbreak", color: "#dc2626", severity: "high" },
  { label: "Fuite de secret", color: "#b91c1c", severity: "high" },
  { label: "Donnée personnelle (PII)", color: "#f59e0b", severity: "medium" },
  { label: "Toxicité", color: "#f97316", severity: "medium" },
  { label: "Légitime", color: "#10b981", severity: "low" },
];

function rand(min, max) {
  return min + Math.random() * (max - min);
}

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

/**
 * Generate mock predictions for a manually-selected text segment.
 * Checks the segment against known patterns and always includes a
 * "Légitime" fallback. Returns a span object ready for TextResultView.
 */
export function mockPredictSpan(text, start, end, assignedLabel) {
  const segment = text.slice(start, end);

  // Build predictions: check segment against each known pattern
  const predictions = [];
  for (const { re, label } of TEXT_PATTERNS) {
    const test = new RegExp(re.source, re.flags.replace("g", ""));
    if (test.test(segment)) {
      predictions.push({
        label,
        probability: 0.55 + Math.random() * 0.35,
      });
    }
  }
  // Always include a "Légitime" fallback
  predictions.push({
    label: "Légitime",
    probability: 0.08 + Math.random() * 0.2,
  });

  // If user assigned a label manually, boost it to the top
  if (assignedLabel && assignedLabel !== "Légitime") {
    const existing = predictions.find((p) => p.label === assignedLabel);
    if (existing) {
      existing.probability = 0.85 + Math.random() * 0.1;
    } else {
      predictions.unshift({
        label: assignedLabel,
        probability: 0.85 + Math.random() * 0.1,
      });
    }
  }

  // Sort by probability descending
  predictions.sort((a, b) => b.probability - a.probability);

  // Normalize so probabilities sum to ~1
  const sum = predictions.reduce((acc, p) => acc + p.probability, 0);
  predictions.forEach((p) => {
    p.probability = Number((p.probability / sum).toFixed(3));
  });

  const top = predictions[0];
  const labelInfo = TEXT_LABELS.find((l) => l.label === top.label);

  return {
    id: `span-manual-${Date.now()}`,
    start_char: start,
    end_char: end,
    text: segment,
    classification: top.label.toLowerCase().replace(/\s+/g, "_"),
    label: top.label,
    description: "Segment sélectionné manuellement par l'utilisateur.",
    probability: top.probability,
    severity: labelInfo?.severity || "medium",
    proposals: predictions.slice(1).map((p) => ({
      ...p,
      probability: Number(p.probability.toFixed(3)),
    })),
    decision: null,
    drawn: true,
  };
}

/**
 * Generate a document analysis result with page-level multi-label
 * classifications and per-bbox annotations.
 *
 * @param {object} inputData  backend InputData (metadata + pages[])
 */
export async function mockDocumentAnalysis(inputData) {
  await delay(500 + Math.random() * 500);

  const pageCount = inputData?.pages?.length || 1;
  const pages = [];

  for (let p = 0; p < pageCount; p++) {
    const width = 612;
    const height = 792;

    // Page-level multi-label classification (2-4 labels)
    const labelCount = 2 + Math.floor(Math.random() * 3);
    const shuffled = [...DOC_CLASSIFICATIONS].sort(() => Math.random() - 0.5);
    const classifications = shuffled
      .slice(0, labelCount)
      .map((label) => ({
        label,
        probability: Number(rand(0.4, 0.95).toFixed(3)),
      }))
      .sort((a, b) => b.probability - a.probability);

    // Bboxes (3-7 per page)
    const bboxCount = 3 + Math.floor(Math.random() * 5);
    const bboxes = [];
    for (let b = 0; b < bboxCount; b++) {
      const cls = pick(BBOX_CLASSIFICATIONS);
      const bw = rand(80, 250);
      const bh = rand(20, 60);
      bboxes.push({
        id: `bbox-${p}-${b}`,
        x: rand(40, width - bw - 40),
        y: rand(60, height - bh - 60),
        width: bw,
        height: bh,
        classification: cls.label,
        color: cls.color,
        description: `Zone identifiée comme « ${cls.label} » par le modèle de classification visuelle.`,
        probability: Number(rand(0.55, 0.98).toFixed(3)),
        severity: rand(0, 1) > 0.7 ? "medium" : "low",
        proposals: [
          { label: pick(BBOX_CLASSIFICATIONS).label, probability: Number(rand(0.2, 0.5).toFixed(3)) },
          { label: pick(BBOX_CLASSIFICATIONS).label, probability: Number(rand(0.1, 0.3).toFixed(3)) },
        ],
        decision: null,
      });
    }

    pages.push({
      page_number: p + 1,
      width,
      height,
      classifications,
      bboxes,
    });
  }

  return {
    kind: "document",
    pages,
    metadata: { mock: true, source: "web" },
  };
}

// Available classification labels for the bbox editor (user-drawn bboxes).
export const BBOX_LABELS = BBOX_CLASSIFICATIONS;
