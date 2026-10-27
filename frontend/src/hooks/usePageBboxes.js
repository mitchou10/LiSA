import { useCallback, useEffect, useState } from "react";
import { addPageBbox, deletePageBbox, listPageBboxes } from "../lib/api";

/**
 * The boxes users drew on the pages of a run (kept in the database, blurred
 * on export): { boxes, add(pageNumber, box), remove(id) }.
 */
export function usePageBboxes(runId) {
  const [boxes, setBoxes] = useState([]);

  useEffect(() => {
    setBoxes([]);
    if (!runId) return undefined;
    let active = true;
    listPageBboxes(runId)
      .then((rows) => active && setBoxes(rows))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [runId]);

  const add = useCallback(
    async (pageNumber, box) => {
      try {
        const row = await addPageBbox(runId, { page_number: pageNumber, ...box });
        setBoxes((prev) => [...prev, row]);
      } catch {
        /* the box is simply not added */
      }
    },
    [runId]
  );
  const remove = useCallback(
    async (id) => {
      try {
        await deletePageBbox(runId, id);
        setBoxes((prev) => prev.filter((b) => b.id !== id));
      } catch {
        /* the box stays */
      }
    },
    [runId]
  );

  return { boxes, add, remove };
}
