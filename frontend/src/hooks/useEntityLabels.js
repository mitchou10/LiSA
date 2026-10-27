import { useEffect, useMemo, useState } from "react";
import { getDefinitions } from "../lib/api";

/**
 * The labels one can give to a box drawn by hand: what the run's project
 * looks for, then whatever was found in this run (the only source for a
 * default run, which has no project).
 */
export function useEntityLabels(run, pages) {
  const projectId = run?.project_id;
  const [defined, setDefined] = useState([]);

  useEffect(() => {
    setDefined([]);
    if (!projectId) return undefined;
    let active = true;
    getDefinitions(projectId, "entities")
      .then((rows) => active && setDefined(rows.filter((r) => r.enabled).map((r) => r.label)))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [projectId]);

  return useMemo(() => {
    const found = pages.flatMap((p) => p.entities.map((e) => e.label));
    return [...new Set([...defined, ...found])].filter(Boolean).sort((a, b) => a.localeCompare(b));
  }, [defined, pages]);
}
