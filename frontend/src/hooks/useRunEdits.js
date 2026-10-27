import { useCallback, useEffect, useState } from "react";
import {
  deleteBoxOverride,
  listBoxOverrides,
  listReplacements,
  setBoxOverride,
  setReplacement,
} from "../lib/api";
import { overrideKey, replacementKey } from "../lib/runEdits";

/**
 * What the user changed on a run, kept in the database:
 * - replacements: Map(key of a text -> text to write instead), set(text, value)
 * - overrides: Map("page:entity:index" -> corrected box), correct(...), reset(id)
 */
export function useRunEdits(runId) {
  const [replacements, setReplacements] = useState(() => new Map());
  const [overrides, setOverrides] = useState(() => new Map());

  useEffect(() => {
    setReplacements(new Map());
    setOverrides(new Map());
    if (!runId) return undefined;
    let active = true;
    listReplacements(runId)
      .then((rows) => active && setReplacements(new Map(rows.map((r) => [r.key, r.replacement]))))
      .catch(() => {});
    listBoxOverrides(runId)
      .then(
        (rows) =>
          active &&
          setOverrides(new Map(rows.map((o) => [overrideKey(o.page_number, o.entity_id, o.bbox_index), o])))
      )
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [runId]);

  const set = useCallback(
    async (text, value) => {
      const key = replacementKey(text);
      const next = value.trim();
      const previous = replacements.get(key);
      if ((previous ?? "") === next) return;
      const apply = (v) =>
        setReplacements((prev) => {
          const map = new Map(prev);
          if (v) map.set(key, v);
          else map.delete(key);
          return map;
        });
      apply(next);
      try {
        await setReplacement(runId, text, next);
      } catch {
        apply(previous);
      }
    },
    [runId, replacements]
  );

  const correct = useCallback(
    async (pageNumber, entityId, index, box) => {
      const key = overrideKey(pageNumber, entityId, index);
      const previous = overrides.get(key);
      setOverrides((prev) => new Map(prev).set(key, { ...previous, ...box }));
      try {
        const row = await setBoxOverride(runId, {
          page_number: pageNumber,
          entity_id: entityId,
          bbox_index: index,
          ...box,
        });
        setOverrides((prev) => new Map(prev).set(key, row));
      } catch {
        setOverrides((prev) => {
          const map = new Map(prev);
          if (previous) map.set(key, previous);
          else map.delete(key);
          return map;
        });
      }
    },
    [runId, overrides]
  );

  const reset = useCallback(
    async (key) => {
      const row = overrides.get(key);
      if (!row?.id) return;
      try {
        await deleteBoxOverride(runId, row.id);
        setOverrides((prev) => {
          const map = new Map(prev);
          map.delete(key);
          return map;
        });
      } catch {
        /* the correction stays */
      }
    },
    [runId, overrides]
  );

  return { replacements, set, overrides, correct, reset };
}
