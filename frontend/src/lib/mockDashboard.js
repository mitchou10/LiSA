// Mock dashboard stats generator.
// Produces a realistic DashboardStats payload matching the backend schema
// (see backend/app/schemas/analytics.py → DashboardStats).
// Used as a fallback when the backend is unavailable.

const DETECTION_TYPES = [
  "prompt_injection",
  "jailbreak",
  "secret_leak",
  "pii",
  "toxicity",
  "banned_topic",
  "bias",
  "hallucination",
];

const SEVERITIES = ["high", "medium", "low"];

const USERS = [
  "alice",
  "bob",
  "charlie",
  "diana",
  "eve",
  "frank",
  "grace",
  "heidi",
];

// Deterministic pseudo-random based on a seed (string → number).
function seeded(seed) {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.codePointAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h += 0x6d2b79f5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function isoDate(d) {
  return d.toISOString().slice(0, 10);
}

function isoDateTime(d) {
  return d.toISOString();
}

/**
 * Generate mock dashboard stats.
 *
 * @param {{ userId?: string, days?: number }} opts
 * @returns {object} DashboardStats-shaped payload.
 */
export function mockDashboardStats({ userId, days = 30 } = {}) {
  const seed = `${userId || "all"}-${days}`;
  const rand = seeded(seed);

  const now = new Date();
  const start = new Date(now);
  start.setDate(start.getDate() - days);

  // ── Time series (one bucket per day) ───────────────────────────────
  const timeseries = [];
  for (let i = 0; i < days; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    const weekday = d.getDay(); // 0=Sun … 6=Sat
    const weekendBoost = weekday === 0 || weekday === 6 ? 0.3 : 1;
    const ramp = 1 + i / days; // slight upward trend
    const tasks = Math.round(
      (8 + rand() * 25) * weekendBoost * ramp
    );
    const detections = Math.round(tasks * (2 + rand() * 3));
    const flagged = Math.round(detections * (0.08 + rand() * 0.22));
    timeseries.push({
      date: isoDate(d),
      tasks,
      detections,
      flagged,
    });
  }

  // ── Aggregated totals ─────────────────────────────────────────────
  const totalTasks = timeseries.reduce((s, b) => s + b.tasks, 0);
  const totalDetections = timeseries.reduce((s, b) => s + b.detections, 0);
  const totalFlagged = timeseries.reduce((s, b) => s + b.flagged, 0);
  const flaggedRate = totalDetections
    ? totalFlagged / totalDetections
    : 0;

  // ── By detection type ──────────────────────────────────────────────
  const byType = DETECTION_TYPES.map((type) => {
    const total = Math.round(5 + rand() * 60);
    const flagged = Math.round(total * (0.1 + rand() * 0.5));
    return { type, total, flagged };
  })
    .sort((a, b) => b.flagged - a.flagged)
    // Keep only types with at least 1 flagged for a cleaner chart
    .filter((d) => d.flagged > 0);

  // ── By severity ───────────────────────────────────────────────────
  const severityCounts = SEVERITIES.map((sev) => {
    let max;
    if (sev === "high") max = 15;
    else if (sev === "medium") max = 30;
    else max = 50;
    return {
      severity: sev,
      count: Math.round(2 + rand() * max),
    };
  });

  // ── By user (only when not filtered by a specific user) ────────────
  const byUser = userId
    ? []
    : USERS.slice(0, 5 + Math.floor(rand() * 3)).map((u) => {
        const tasks = Math.round(10 + rand() * 80);
        const detections = Math.round(tasks * (2 + rand() * 2));
        const flagged = Math.round(detections * (0.05 + rand() * 0.25));
        return { user_id: u, tasks, detections, flagged };
      }).sort((a, b) => b.flagged - a.flagged);

  // ── Alerts (recent medium/high findings) ──────────────────────────
  const alertCount = 6 + Math.floor(rand() * 8);
  const alerts = Array.from({ length: alertCount }, (_, i) => {
    const type = DETECTION_TYPES[Math.floor(rand() * DETECTION_TYPES.length)];
    const severity = rand() > 0.4 ? "high" : "medium";
    const user = userId || USERS[Math.floor(rand() * USERS.length)];
    const when = new Date(now);
    when.setMinutes(when.getMinutes() - Math.floor(rand() * days * 24 * 60));
    return {
      task_id: crypto.randomUUID(),
      user_id: user,
      type,
      severity,
      action: rand() > 0.5 ? "flagged" : "blocked",
      confidence: 0.55 + rand() * 0.44,
      created_at: isoDateTime(when),
    };
  }).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  return {
    user_id: userId || null,
    since: isoDateTime(start),
    generated_at: isoDateTime(now),
    total_tasks: totalTasks,
    total_detections: totalDetections,
    total_flagged: totalFlagged,
    flagged_rate: flaggedRate,
    by_type: byType,
    by_severity: severityCounts,
    by_user: byUser,
    timeseries,
    alerts,
  };
}
