import { useCallback, useEffect, useRef, useState } from "react";
import { getTask, getTaskChildren, startDefaultRun, startRun } from "../lib/api";

const POLL_MS = 1500;
const TERMINAL = ["success", "error", "revoked"];

/**
 * Start a run and follow it until it ends.
 *
 * `steps` come from the backend in execution order; each is merged with the
 * live state of its task (status, progress, output, error). The run is over
 * when its parent task reaches a terminal state.
 *
 * With a `projectId`, the run applies what that project looks for; without
 * one, it applies the default definitions (PII entities, safety checks).
 */
export function useProjectRun() {
  const [run, setRun] = useState(null); // { id, status, steps: [...] }
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const cancelled = useRef(false);

  useEffect(() => () => void (cancelled.current = true), []);

  const reset = useCallback(() => {
    setRun(null);
    setError(null);
  }, []);

  const start = useCallback(async (projectId, body) => {
    cancelled.current = false;
    setError(null);
    setRunning(true);
    setRun(null);
    try {
      const started = projectId
        ? await startRun(projectId, body)
        : await startDefaultRun(body);
      let steps = started.steps.map((s) => ({ ...s, progress: 0 }));
      setRun({ id: started.id, status: started.status, steps });

      // The loop ends with the parent task; a hung worker is the user's to cancel.
      while (!cancelled.current) {
        await new Promise((r) => setTimeout(r, POLL_MS));
        const [parent, children] = await Promise.all([
          getTask(started.id),
          getTaskChildren(started.id),
        ]);
        const byId = new Map(children.map((c) => [c.id, c]));
        steps = steps.map((s) => {
          const task = byId.get(s.task_id);
          if (!task) return s;
          return {
            ...s,
            status: task.status,
            progress: task.progress,
            // Still waiting until it leaves its "awaiting" state.
            waiting: task.input_data?.awaiting !== undefined,
            output: task.output_data,
            error: task.error,
            // Compute time, once the worker has finished (queue wait excluded).
            duration: task.duration_seconds,
          };
        });
        setRun({
          id: started.id,
          status: parent.status,
          duration: parent.duration_seconds,
          steps,
        });
        if (TERMINAL.includes(parent.status)) break;
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }, []);

  return { run, running, error, start, reset };
}
