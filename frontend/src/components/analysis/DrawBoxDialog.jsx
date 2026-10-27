import { useEffect, useRef, useState } from "react";
import { Dialog } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { colorFor } from "../../lib/runModel";
import { cn } from "../../lib/utils";
import { useI18n } from "../../lib/i18n.jsx";

/**
 * Opens when a box was drawn on a page: shows what is inside it (a crop of
 * the page) and asks which label it is. The label is picked in the list, or
 * typed when it is not there yet.
 */
export default function DrawBoxDialog({ pending, labels, onSave, onCancel }) {
  const { t } = useI18n();
  const canvas = useRef(null);
  const [label, setLabel] = useState("");

  useEffect(() => {
    setLabel("");
  }, [pending]);

  // Crop the page to the box, on a canvas.
  useEffect(() => {
    if (!pending) return undefined;
    let active = true;
    const img = new Image();
    img.onload = () => {
      const el = canvas.current;
      if (!active || !el) return;
      const { box } = pending;
      const sx = box.x * img.naturalWidth;
      const sy = box.y * img.naturalHeight;
      const sw = Math.max(1, box.width * img.naturalWidth);
      const sh = Math.max(1, box.height * img.naturalHeight);
      el.width = sw;
      el.height = sh;
      el.getContext("2d").drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh);
    };
    img.src = pending.url;
    return () => {
      active = false;
    };
  }, [pending]);

  const value = label.trim();
  const submit = (e) => {
    e.preventDefault();
    if (value) onSave(value);
  };

  return (
    <Dialog open={!!pending} onClose={onCancel} title={t("run.doc.drawTitle")}>
      <form onSubmit={submit} className="space-y-4">
        <div className="flex justify-center rounded-lg border border-border bg-white p-2">
          <canvas ref={canvas} className="max-h-48 max-w-full object-contain" />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="draw-label">
            {t("run.doc.drawLabel")}
          </label>
          {labels.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {labels.map((l) => (
                <button
                  type="button"
                  key={l}
                  onClick={() => setLabel(l)}
                  className={cn(
                    "rounded-full border px-2.5 py-0.5 text-xs transition-colors",
                    value === l
                      ? "border-transparent text-white"
                      : "border-border text-muted-foreground hover:text-foreground"
                  )}
                  style={value === l ? { backgroundColor: colorFor(l) } : undefined}
                >
                  {l}
                </button>
              ))}
            </div>
          )}
          <Input
            id="draw-label"
            value={label}
            maxLength={255}
            autoFocus
            placeholder={t("run.doc.drawOther")}
            onChange={(e) => setLabel(e.target.value)}
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onCancel}>
            {t("projects.cancel")}
          </Button>
          <Button type="submit" disabled={!value}>
            {t("projects.save")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
