// What "the same text" means for a replacement: same words, whatever the case
// or the spacing. Must match the backend (app.models.text_replacement).
export const replacementKey = (text) => text.split(/\s+/).filter(Boolean).join(" ").toLowerCase();

export const overrideKey = (pageNumber, entityId, index) => `${pageNumber}:${entityId}:${index}`;

/** The pages with the boxes users corrected in place of the detected ones. */
export function withOverrides(pages, overrides) {
  if (overrides.size === 0) return pages;
  return pages.map((page) => ({
    ...page,
    entities: page.entities.map((e) => ({
      ...e,
      bboxes: (e.bboxes ?? []).map((b, i) => {
        const o = overrides.get(overrideKey(page.number, e.id, i));
        return o ? { x: o.x, y: o.y, width: o.width, height: o.height } : b;
      }),
    })),
  }));
}

/** The distinct texts found in the run: [{ key, text, label, count }], most frequent first. */
export function distinctTexts(pages) {
  const groups = new Map();
  for (const page of pages)
    for (const e of page.entities) {
      const key = replacementKey(e.text);
      if (!key) continue;
      const g = groups.get(key);
      if (g) g.count += 1;
      else groups.set(key, { key, text: e.text, label: e.label, count: 1 });
    }
  return [...groups.values()].sort((a, b) => b.count - a.count || a.text.localeCompare(b.text));
}
