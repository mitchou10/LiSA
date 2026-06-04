import { createContext, useContext, useState, useMemo } from "react";

export const translations = {
  en: {
    "app.subtitle": "Jailbreak & prompt injection detection — monitoring",
    "nav.analyze": "Analysis",
    "nav.services": "Services & Tasks",

    "analyze.input.title": "Input",
    "analyze.input.desc": "Pick a format then run the analysis (Ctrl/Cmd + Enter).",
    "analyze.tab.text": "Text",
    "analyze.tab.json": "JSON",
    "analyze.tab.url": "URL",
    "analyze.text.placeholder": "Paste or type the text to analyze…",
    "analyze.url.hint": "The URL content will be fetched and analyzed (mock).",
    "analyze.run": "Analyze",
    "analyze.running": "Analyzing…",
    "analyze.shortcut": "Ctrl/Cmd + Enter",
    "analyze.results.title": "Results",
    "analyze.results.desc": "Overall verdict and per-scanner score.",
    "analyze.error.json": "Invalid JSON. Please check the syntax.",
    "analyze.error.url": "Invalid URL. It must start with http:// or https://",
    "analyze.error.generic": "An error occurred.",

    "results.empty": "Run an analysis to see results here.",
    "results.verdict.danger": "Suspicious content detected",
    "results.verdict.safe": "No risk detected",
    "results.detected": "Detected",
    "results.ok": "OK",
    "results.score": "Score",
    "results.processTime": "Processing time",
    "results.summary": "{flagged} issue(s) detected out of {total} checks.",
    "results.passed": "{count} checks passed",
    "results.details": "Details",
    "results.service": "Service",
    "results.page": "Page {n}",
    "scanner.PromptInjection": "Prompt Injection / Jailbreak",
    "scanner.Secrets": "Secrets / Sensitive data",
    "scanner.Toxicity": "Toxicity",

    "detection.jailbreak": "Jailbreak",
    "detection.prompt_injection": "Prompt Injection",
    "detection.secret_leak": "Secret Leak",
    "detection.sensitive_data_exposure": "Sensitive Data Exposure",
    "detection.toxicity": "Toxicity",
    "detection.pii": "Personal Data (PII)",
    "detection.banned_topic": "Banned Topic",
    "detection.bias": "Bias",
    "detection.hallucination": "Hallucination",
    "detection.malicious_code": "Malicious Code",
    "detection.unknown": "Detector",
    "detection.entities": "Detected entities",
    "detection.topics": "Matched topics",
    "severity.low": "Low",
    "severity.medium": "Medium",
    "severity.high": "High",
    "action.allow": "Allow",
    "action.redact": "Redact",
    "action.block": "Block",

    "services.title": "Services",
    "services.desc": "Status of connected workers.",
    "services.in": "in",
    "services.out": "out",
    "services.quota": "quota",
    "graph.title": "Execution graph",
    "graph.desc": "Track tasks and their sub-tasks (id, route, status).",
    "status.pending": "Pending",
    "status.running": "Running",
    "status.success": "Success",
    "status.error": "Error",

    "health.online": "API online",
    "health.offline": "API offline",
    "health.checking": "Checking…",

    "task.created": "Task created",
    "task.id": "Task ID",
    "task.status": "Status",
  },
  fr: {
    "app.subtitle": "Détection de jailbreak & prompt injection — supervision",
    "nav.analyze": "Analyse",
    "nav.services": "Services & Tâches",

    "analyze.input.title": "Entrée",
    "analyze.input.desc": "Choisissez un format puis lancez l'analyse (Ctrl/Cmd + Entrée).",
    "analyze.tab.text": "Texte",
    "analyze.tab.json": "JSON",
    "analyze.tab.url": "URL",
    "analyze.text.placeholder": "Collez ou écrivez le texte à analyser…",
    "analyze.url.hint": "Le contenu de l'URL sera récupéré et analysé (mock).",
    "analyze.run": "Analyser",
    "analyze.running": "Analyse…",
    "analyze.shortcut": "Ctrl/Cmd + Entrée",
    "analyze.results.title": "Résultats",
    "analyze.results.desc": "Verdict global et score par scanner.",
    "analyze.error.json": "JSON invalide. Vérifiez la syntaxe.",
    "analyze.error.url": "URL invalide. Elle doit commencer par http:// ou https://",
    "analyze.error.generic": "Une erreur est survenue.",

    "results.empty": "Lancez une analyse pour voir les résultats ici.",
    "results.verdict.danger": "Contenu suspect détecté",
    "results.verdict.safe": "Aucun risque détecté",
    "results.detected": "Détecté",
    "results.ok": "OK",
    "results.score": "Score",
    "results.processTime": "Temps de traitement",
    "results.summary": "{flagged} problème(s) détecté(s) sur {total} contrôles.",
    "results.passed": "{count} contrôles OK",
    "results.details": "Détails",
    "results.service": "Service",
    "results.page": "Page {n}",
    "scanner.PromptInjection": "Prompt Injection / Jailbreak",
    "scanner.Secrets": "Secrets / Données sensibles",
    "scanner.Toxicity": "Toxicité",

    "detection.jailbreak": "Jailbreak",
    "detection.prompt_injection": "Prompt Injection",
    "detection.secret_leak": "Fuite de secrets",
    "detection.sensitive_data_exposure": "Exposition de données sensibles",
    "detection.toxicity": "Toxicité",
    "detection.pii": "Données personnelles (PII)",
    "detection.banned_topic": "Sujet interdit",
    "detection.bias": "Biais",
    "detection.hallucination": "Hallucination",
    "detection.malicious_code": "Code malveillant",
    "detection.unknown": "Détecteur",
    "detection.entities": "Entités détectées",
    "detection.topics": "Sujets correspondants",
    "severity.low": "Faible",
    "severity.medium": "Moyen",
    "severity.high": "Élevé",
    "action.allow": "Autoriser",
    "action.redact": "Masquer",
    "action.block": "Bloquer",

    "services.title": "Services",
    "services.desc": "État des workers connectés.",
    "services.in": "in",
    "services.out": "out",
    "services.quota": "quota",
    "graph.title": "Graphe d'exécution",
    "graph.desc": "Suivi des tâches et de leurs sous-tâches (id, route, statut).",
    "status.pending": "En attente",
    "status.running": "En cours",
    "status.success": "Succès",
    "status.error": "Erreur",

    "health.online": "API en ligne",
    "health.offline": "API hors ligne",
    "health.checking": "Vérification…",

    "task.created": "Tâche créée",
    "task.id": "ID de tâche",
    "task.status": "Statut",
  },
};

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    return localStorage.getItem("lisa_lang") || "en";
  });

  const value = useMemo(() => {
    const setLanguage = (l) => {
      localStorage.setItem("lisa_lang", l);
      setLang(l);
    };
    const t = (key) => translations[lang]?.[key] ?? translations.en[key] ?? key;
    return { lang, setLanguage, t };
  }, [lang]);

  return (
    <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useI18n must be used within LanguageProvider");
  return ctx;
}
