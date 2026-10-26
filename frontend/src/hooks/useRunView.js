import { useEffect, useState } from "react";
import { getServices, getTask, getTaskChildren } from "../lib/api";

const POLL_MS = 1500;
const TERMINAL = ["success", "error", "revoked"];

// The workers' service names, as the steps of a run call them.
const STEP_OF_SERVICE = {
  "liteparse-ocr": "parser",
  ner: "ner",
  relation: "relation",
  classification: "classification",
  safety: "safety",
  "image-classification": "image_classification",
  "anonymize-v2": "anonymize",
};

/**
 * Follow a run that was started earlier, from its parent task id: the same
 * `{ id, status, duration, steps }` the live run has, rebuilt from the tasks
 * (each child is named after its service) and refreshed until the run ends.
 *
 * `source` is what the text run was sent as, read back from the tasks, so the
 * document can be drawn without the parser. `isRun` is false when the task is
 * not a run (no known step under it).
 */
export function useRunView(taskId) {
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    let active = true;
    let timer = null;
    setState({ loading: true });

    const load = async () => {
      try {
        const [parent, children, services] = await Promise.all([
          getTask(taskId),
          getTaskChildren(taskId).catch(() => []),
          getServices().catch(() => []),
        ]);
        if (!active) return;
        const names = new Map((Array.isArray(services) ? services : []).map((s) => [s.id, s.name]));
        const ordered = [...children].sort((a, b) => a.created_at.localeCompare(b.created_at));
        const steps = ordered
          .map((task) => ({ task, step: STEP_OF_SERVICE[names.get(task.service_id)] }))
          .filter((s) => s.step)
          .map(({ task, step }) => ({
            task_id: task.id,
            step,
            status: task.status,
            progress: task.progress,
            waiting: task.input_data?.awaiting !== undefined,
            output: task.output_data,
            error: task.error,
            duration: task.duration_seconds,
          }));
        const pages = ordered.find((c) => c.input_data?.pages)?.input_data.pages ?? [];
        setState({
          loading: false,
          parent,
          isRun: steps.length > 0,
          run: { id: parent.id, status: parent.status, duration: parent.duration_seconds, steps },
          source: steps.some((s) => s.step === "parser")
            ? { kind: "files" }
            : {
                kind: "text",
                pages: pages.map((p) => ({ number: p.page_number, content: p.content ?? "" })),
              },
        });
        if (!TERMINAL.includes(parent.status)) timer = setTimeout(load, POLL_MS);
      } catch (error) {
        if (active) setState({ loading: false, error });
      }
    };
    load();

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [taskId]);

  return state;
}
