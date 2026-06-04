// Données mockées pour les services et les tâches.
// Une tâche possède un id, une route, des enfants (children) et un statut,
// formant un petit graphe d'exécution.

export const SERVICES = [
  {
    name: "LiSA",
    in_queue: "lisa_queue_in",
    out_queue: "lisa_queue_out",
    quotas: 5000,
    status: "online",
  },
  {
    name: "guard",
    in_queue: "in_queue_python",
    out_queue: "example_out_queue",
    quotas: 1000,
    status: "online",
  },
  {
    name: "analyser",
    in_queue: "analyser_queue_in",
    out_queue: "analyser_queue_out",
    quotas: 1000,
    status: "degraded",
  },
];

// status: "pending" | "running" | "success" | "error"
export const TASKS = [
  {
    id: "task-001",
    route: "/analyze",
    service: "LiSA",
    status: "success",
    children: ["task-002", "task-003"],
  },
  {
    id: "task-002",
    route: "/guard/prompt-injection",
    service: "guard",
    status: "success",
    children: ["task-004"],
  },
  {
    id: "task-003",
    route: "/guard/secrets",
    service: "guard",
    status: "running",
    children: [],
  },
  {
    id: "task-004",
    route: "/analyser/zero-shot",
    service: "analyser",
    status: "error",
    error: "Timeout after 30s: the analyser service did not respond.",
    children: [],
  },
];
