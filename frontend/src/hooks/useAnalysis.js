import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { submitTask, getTask, getServices } from "../lib/api";
import { mockAnalyze } from "../lib/mockApi";
import { SERVICES as MOCK_SERVICES } from "../lib/mockData";
import { useAuth } from "../lib/auth";

const TERMINAL = new Set(["success", "error", "revoked"]);
const POLL_INTERVAL = 1200;
const MAX_POLLS = 100;

// When true, the hook always uses mock data regardless of backend availability.
// When false (default), it tries the real backend and only falls back to mocks
// in dev mode when the API is unreachable.
const FORCE_MOCKS =
  import.meta.env.VITE_USE_MOCKS === "true" ||
  import.meta.env.VITE_USE_MOCKS === "1";

// Merge every finished child's `Analyse` output into a single pages[] tree.
function consolidate(runs) {
  const byPage = new Map();
  for (const run of runs) {
    const pages = run.task?.output_data?.pages || [];
    for (const page of pages) {
      const key = page.page_number ?? 1;
      if (!byPage.has(key))
        byPage.set(key, { page_number: key, detections: [] });
      const dets = (page.detections || []).map((d) => ({
        ...d,
        service: run.service.name,
      }));
      byPage.get(key).detections.push(...dets);
    }
  }
  const pages = [...byPage.values()].sort(
    (a, b) => (a.page_number ?? 0) - (b.page_number ?? 0)
  );
  return pages.length ? { pages } : null;
}

/**
 * Shared analysis engine used by every analysis tab (text, file, …).
 *
 * A tab provides an `inputData` builder (a function returning the backend
 * `InputData` payload). The hook handles service discovery, fan-out task
 * creation, polling and mock fallback.
 *
 * @param {object}   [opts]
 * @param {(inputData: object) => Promise<object>} [opts.mockFn]
 *   Custom mock generator. When the backend is unavailable, this function is
 *   called with the full `InputData` payload and should return a rich result
 *   object (text spans, document bboxes, …). Falls back to the legacy
 *   `mockAnalyze` scanner when omitted.
 */
export function useAnalysis(opts = {}) {
  const { user } = useAuth();
  const userId = user?.id || "web-user";
  const mockFnRef = useRef(opts.mockFn);
  mockFnRef.current = opts.mockFn;

  const [services, setServices] = useState([]);
  const [servicesReal, setServicesReal] = useState(false);
  const [selected, setSelected] = useState(() => new Set());

  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [group, setGroup] = useState(null);
  const [runs, setRuns] = useState([]);
  const [mockResult, setMockResult] = useState(null);

  const pollRef = useRef(null);
  const cancelRef = useRef(false);

  // Load available services (fall back to mock data when the API is down
  // or when mocks are explicitly forced via VITE_USE_MOCKS).
  useEffect(() => {
    if (FORCE_MOCKS) {
      setServices(MOCK_SERVICES);
      setServicesReal(false);
      setSelected(new Set(MOCK_SERVICES.map((s) => s.id)));
      return;
    }

    let active = true;
    getServices()
      .then((data) => {
        if (!active) return;
        const list = Array.isArray(data) && data.length ? data : MOCK_SERVICES;
        const real = Array.isArray(data) && data.length > 0;
        setServices(list);
        setServicesReal(real);
        setSelected(new Set(list.map((s) => s.id)));
      })
      .catch(() => {
        if (!active) return;
        // In dev, fall back to mock services so the UI is still usable.
        // In prod, keep the empty list — the error will surface on analyze.
        const useMocks = import.meta.env.DEV;
        setServices(useMocks ? MOCK_SERVICES : []);
        setServicesReal(false);
        setSelected(
          new Set((useMocks ? MOCK_SERVICES : []).map((s) => s.id))
        );
      });
    return () => {
      active = false;
    };
  }, []);

  // Stop polling on unmount.
  useEffect(
    () => () => {
      cancelRef.current = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    },
    []
  );

  const toggleService = useCallback((id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(
    () => setSelected(new Set(services.map((s) => s.id))),
    [services]
  );
  const clearAll = useCallback(() => setSelected(new Set()), []);

  const startPolling = useCallback((childRuns) => {
    const ids = childRuns.map((r) => r.task.id);
    let attempts = 0;

    const tick = async () => {
      if (cancelRef.current) return;
      attempts += 1;
      const tasks = await Promise.all(
        ids.map((id) => getTask(id).catch(() => null))
      );
      setRuns((prev) =>
        prev.map((run) => {
          const fresh = tasks.find((tk) => tk && tk.id === run.task.id);
          return fresh ? { ...run, task: fresh } : run;
        })
      );
      const allDone = tasks.every((tk) => tk && TERMINAL.has(tk.status));
      if (allDone || attempts >= MAX_POLLS) {
        setRunning(false);
        return;
      }
      pollRef.current = setTimeout(tick, POLL_INTERVAL);
    };
    tick();
  }, []);

  /**
   * Run the analysis for a given input.
   * @param {() => object} buildInputData  returns the backend InputData payload
   * @param {string} t  i18n function (for error messages)
   */
  const analyze = useCallback(
    async (buildInputData, t) => {
      setError(null);
      setGroup(null);
      setRuns([]);
      setMockResult(null);
      if (pollRef.current) clearTimeout(pollRef.current);

      let inputData;
      try {
        inputData = buildInputData();
      } catch (err) {
        setError(err?.message || t("analyze.error.generic"));
        return;
      }

      const chosen = services.filter((s) => selected.has(s.id));
      if (chosen.length === 0) {
        setError(t("analyze.services.none"));
        return;
      }

      setRunning(true);

      // Without real services we can't dispatch tasks: run the mock scanner.
      if (!servicesReal) {
        try {
          if (mockFnRef.current) {
            setMockResult(await mockFnRef.current(inputData));
          } else {
            const joined = inputData.pages.map((p) => p.content).join("\n\n");
            setMockResult(await mockAnalyze(joined));
          }
        } catch (err) {
          setError(err.message || t("analyze.error.generic"));
        } finally {
          setRunning(false);
        }
        return;
      }

      try {
        // 1) Create the parent "group" task (no service of its own).
        const parent = await submitTask({ userId, inputData });
        setGroup(parent);

        // 2) Fan out one child task per selected service.
        const children = await Promise.all(
          chosen.map((svc) =>
            submitTask({
              userId,
              inputData,
              serviceId: svc.id,
              parentTaskId: parent.id,
            }).then((task) => ({ service: svc, task }))
          )
        );
        setRuns(children);

        // 3) Poll children for intermediate + final results.
        cancelRef.current = false;
        startPolling(children);
      } catch (err) {
        setError(err.message || t("analyze.error.generic"));
        setRunning(false);
      }
    },
    [services, selected, servicesReal, startPolling]
  );

  const reset = useCallback(() => {
    setError(null);
    setGroup(null);
    setRuns([]);
    setMockResult(null);
    setRunning(false);
    if (pollRef.current) clearTimeout(pollRef.current);
  }, []);

  const consolidated = useMemo(() => consolidate(runs), [runs]);
  const doneCount = runs.filter((r) => TERMINAL.has(r.task?.status)).length;
  const result = mockResult ?? consolidated;
  const showLoading = running && !result;

  return {
    // services
    services,
    servicesReal,
    selected,
    toggleService,
    selectAll,
    clearAll,
    // run state
    running,
    error,
    group,
    runs,
    doneCount,
    result,
    showLoading,
    // result mutation (for rich mock views: validate/reject spans & bboxes)
    setMockResult,
    // actions
    analyze,
    reset,
  };
}
