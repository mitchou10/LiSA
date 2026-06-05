// Mock d'analyse : génère un résultat déterministe basé sur le contenu.
// Forme alignée sur le schéma backend `Analyse` (liste de DetectionResult).
// Remplaçable plus tard par un vrai appel API.

const JAILBREAK_PATTERNS = [
  /ignore (all|previous|the above)/i,
  /disregard (all|previous|your)/i,
  /jailbreak/i,
  /\bDAN\b/,
  /developer mode/i,
  /pretend (you|to be)/i,
  /act as (an? )?(unrestricted|evil|uncensored)/i,
  /bypass (your|the|all) (rules|restrictions|guidelines)/i,
  /system prompt/i,
  /do anything now/i,
];

const INJECTION_PATTERNS = [
  /ignore (all|previous|the above)/i,
  /system prompt/i,
  /new instructions/i,
  /forget (everything|all|the above)/i,
];

const SECRET_PATTERNS = [
  /sk-[a-zA-Z0-9]{10,}/,
  /AKIA[0-9A-Z]{12,}/,
  /(api[_-]?key|password|secret|token)\s*[:=]/i,
  /-----BEGIN (RSA |EC )?PRIVATE KEY-----/,
];

const TOXIC_PATTERNS = [/\b(kill|destroy|hate|attack|idiot|stupid)\b/i];

const PII_PATTERNS = [
  { type: "EMAIL", re: /[\w.+-]+@[\w-]+\.[\w.-]+/g },
  { type: "IBAN", re: /\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b/g },
  { type: "PHONE", re: /\b(?:\+?\d{1,3}[ .-]?)?(?:\d{2,3}[ .-]?){3,4}\b/g },
];

function scoreFor(text, patterns, base) {
  let hits = 0;
  for (const p of patterns) if (p.test(text)) hits += 1;
  if (hits === 0) return Math.min(0.12, base + text.length / 50000);
  return Math.min(0.99, 0.55 + hits * 0.18);
}

function severityFor(score) {
  if (score >= 0.8) return "high";
  if (score >= 0.5) return "medium";
  return "low";
}

function actionFor(flagged, score) {
  if (!flagged) return "allow";
  return score >= 0.8 ? "block" : "redact";
}

function detection(type, predicateKey, score, extra = {}) {
  const flagged = score >= 0.5;
  return {
    type,
    flagged,
    confidence: Number(score.toFixed(3)),
    severity: severityFor(score),
    action: actionFor(flagged, score),
    service_id: `mock-${type}`,
    details: null,
    [predicateKey]: flagged,
    ...extra,
  };
}

function findPII(text) {
  const entities = [];
  let idx = 0;
  for (const { type, re } of PII_PATTERNS) {
    for (const match of text.matchAll(re)) {
      entities.push({
        id: `e${idx++}`,
        type,
        text: match[0],
        start_char: match.index,
        end_char: match.index + match[0].length,
      });
    }
  }
  return entities;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function mockAnalyze(text) {
  await delay(400 + Math.random() * 500);

  const content = typeof text === "string" ? text : JSON.stringify(text);

  const piiEntities = findPII(content);
  const piiScore = piiEntities.length
    ? Math.min(0.99, 0.55 + piiEntities.length * 0.12)
    : 0.05;

  // One detection of every supported type, with type-specific detail fields.
  const detections = [
    detection("jailbreak", "jailbreak", scoreFor(content, JAILBREAK_PATTERNS, 0.02), {
      details: {
        technique: "role-play",
        matched_pattern: "act as an unrestricted AI",
        model: "guard-jailbreak-v2",
      },
    }),
    detection(
      "prompt_injection",
      "prompt_injection",
      scoreFor(content, INJECTION_PATTERNS, 0.02),
      {
        details: {
          injection_type: "instruction-override",
          matched_pattern: "ignore previous instructions",
          position: "user-input",
        },
      }
    ),
    detection("secret_leak", "secret_leak", scoreFor(content, SECRET_PATTERNS, 0.0), {
      details: {
        secret_type: "api_key",
        provider: "OpenAI",
        masked: "sk-****************7890",
      },
    }),
    detection(
      "sensitive_data_exposure",
      "sensitive_data_exposure",
      scoreFor(content, SECRET_PATTERNS, 0.04),
      {
        details: {
          category: "financial",
          source: "internal-document",
          classification: "confidential",
        },
      }
    ),
    detection("toxicity", "toxic", scoreFor(content, TOXIC_PATTERNS, 0.03), {
      details: {
        labels: { insult: 0.71, threat: 0.42, profanity: 0.18 },
        language: "en",
      },
    }),
    detection("pii", "pii", piiScore, {
      entities: piiEntities.length
        ? piiEntities
        : [
            { id: "e0", type: "EMAIL", text: "john.doe@example.com", start_char: 0, end_char: 20 },
            { id: "e1", type: "IBAN", text: "FR7630006000011234567890189", start_char: 25, end_char: 52 },
            { id: "e2", type: "PHONE", text: "+33 6 12 34 56 78", start_char: 60, end_char: 77 },
          ],
      details: { jurisdiction: "GDPR", entity_count: piiEntities.length || 3 },
    }),
    detection("banned_topic", "banned_topic", 0.62, {
      topics: ["competitor", "internal-pricing"],
      details: { policy: "corporate-guidelines", matched: 2 },
    }),
    detection("bias", "bias", 0.41, {
      details: { dimension: "gender", direction: "stereotypical", score: 0.41 },
    }),
    detection("hallucination", "hallucination", 0.73, {
      details: {
        grounding: 0.27,
        unsupported_claims: 3,
        evidence: "no matching source document",
      },
    }),
    detection("malicious_code", "malicious_code", 0.88, {
      details: {
        language: "python",
        category: "reverse-shell",
        cwe: "CWE-78",
      },
    }),
  ];

  return {
    id: `mock-${Date.now()}`,
    pages: [{ page_number: null, detections }],
    error: null,
    metadata: { mock: true },
  };
}
