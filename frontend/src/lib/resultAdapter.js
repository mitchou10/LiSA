// Adapter that transforms a backend `Analyse` result (pages[].detections[])
// into the rich format expected by TextResultView (text + spans[]).
//
// Backend output_data shape (from the worker):
//   {
//     "id": "...",
//     "pages": [
//       {
//         "page_number": 1,
//         "detections": [
//           {
//             "flagged": true,
//             "confidence": 0.85,
//             "severity": "high",
//             "action": "redact",
//             "pii": true,
//             "entities": [
//               { "id": "e0", "type": "EMAIL", "text": "john@example.com",
//                 "start_char": 10, "end_char": 28, "flagged": true,
//                 "confidence": 0.85 }
//             ]
//           }
//         ]
//       }
//     ]
//   }
//
// TextResultView expects:
//   {
//     kind: "text",
//     text: "full text...",
//     spans: [
//       { id, start_char, end_char, text, label, classification,
//         description, probability, severity, proposals, decision }
//     ],
//     metadata: { ... }
//   }

import { TEXT_LABELS } from "./mockResults";

// Map backend entity types (from llm-guard / Presidio) to our TEXT_LABELS.
const ENTITY_TYPE_MAP = {
  EMAIL_ADDRESS: "pii",
  EMAIL: "pii",
  PHONE_NUMBER: "pii",
  IBAN_CODE: "pii",
  CREDIT_CARD: "pii",
  CREDIT_CARD_RE: "pii",
  US_SSN: "pii",
  NRP: "pii",
  PERSON: "pii",
  LOCATION: "pii",
  DATE_TIME: "pii",
  DATE_PERIOD: "pii",
  URL: "pii",
  IP_ADDRESS: "pii",
  US_PASSPORT: "pii",
  US_DRIVER_LICENSE: "pii",
  SECRET: "secret_leak",
  API_KEY: "secret_leak",
  // llm-guard may return these
  PROMPT_INJECTION: "prompt_injection",
  JAILBREAK: "jailbreak",
  TOXICITY: "toxicity",
  BANNED_TOPIC: "banned_topic",
  BIAS: "bias",
  HALLUCINATION: "hallucination",
};

function labelFor(entityType, classification) {
  const cls = classification || ENTITY_TYPE_MAP[entityType || ""] || "unknown";
  const found = TEXT_LABELS.find((l) => l.classification === cls);
  return found || TEXT_LABELS.at(-1); // fallback to "Légitime"
}

function severityFor(detection, entity) {
  if (entity?.flagged && detection?.severity) return detection.severity;
  if (detection?.severity) return detection.severity;
  return "low";
}

/**
 * Convert a backend Analyse result into the TextResultView format.
 *
 * @param {object} analyseResult - The consolidated result from useAnalysis
 *   (has `pages` with `detections` and `entities`).
 * @param {string} originalText - The original text that was submitted
 *   (needed because the backend result doesn't include the raw text).
 * @returns {object|null} A TextResultView-shaped result, or null if the
 *   input doesn't look like a backend Analyse payload.
 */
export function adaptBackendToTextResult(analyseResult, originalText) {
  if (!analyseResult?.pages) return null;

  const spans = [];
  let spanIdx = 0;

  for (const page of analyseResult.pages) {
    const detections = page.detections || [];
    for (const det of detections) {
      const entities = det.entities || [];

      // Case 1: detection has entities with char offsets → create spans
      //         for each entity (e.g. PII from Anonymize, secrets from Secrets).
      for (const entity of entities) {
        if (entity.start_char == null || entity.end_char == null) continue;
        if (entity.start_char < 0) continue;

        const labelInfo = labelFor(entity.type, det.classification);
        spans.push({
          id: entity.id || `span-${spanIdx++}`,
          start_char: entity.start_char,
          end_char: entity.end_char,
          text: entity.text || "",
          classification: labelInfo.classification,
          label: labelInfo.label,
          description: labelInfo.description || "",
          probability: entity.confidence ?? det.confidence ?? 0,
          severity: severityFor(det, entity),
          proposals: labelInfo.proposals || [],
          decision: null,
          service: det.service || entity.service,
        });
        spanIdx++;
      }

      // Case 2: detection is flagged but has no entities (e.g. PromptInjection,
      //         Toxicity — they score the whole text, not specific spans).
      //         Create a span covering the entire text so the user sees the
      //         issue highlighted.
      if (det.flagged && entities.length === 0) {
        const labelInfo = labelFor(null, det.classification);
        spans.push({
          id: `span-${spanIdx++}`,
          start_char: 0,
          end_char: (originalText || "").length,
          text: originalText || "",
          classification: labelInfo.classification,
          label: labelInfo.label,
          description: labelInfo.description || "",
          probability: det.confidence ?? 0,
          severity: det.severity || "medium",
          proposals: labelInfo.proposals || [],
          decision: null,
          service: det.service,
        });
        spanIdx++;
      }
    }
  }

  return {
    kind: "text",
    text: originalText || "",
    spans,
    metadata: { source: "backend", mock: false },
  };
}

/**
 * Extract the original submitted text from an InputData payload.
 */
export function extractText(inputData) {
  if (!inputData?.pages?.length) return "";
  return inputData.pages.map((p) => p.content || "").join("\n\n");
}
