import { Badge } from "../ui/badge";
import { cn } from "../../lib/utils";
import { useI18n } from "../../lib/i18n.jsx";

/**
 * Reusable service picker used by every analysis tab.
 */
export default function ServiceSelector({
  services,
  selected,
  onToggle,
  onSelectAll,
  onClearAll,
}) {
  const { t } = useI18n();

  return (
    <div className="mt-5">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">{t("analyze.services.title")}</p>
          <p className="text-xs text-muted-foreground">
            {t("analyze.services.desc")}
          </p>
        </div>
        <div className="flex gap-2 text-xs">
          <button
            type="button"
            onClick={onSelectAll}
            className="text-muted-foreground hover:text-foreground"
          >
            {t("analyze.services.all")}
          </button>
          <span className="text-border">·</span>
          <button
            type="button"
            onClick={onClearAll}
            className="text-muted-foreground hover:text-foreground"
          >
            {t("analyze.services.clear")}
          </button>
        </div>
      </div>

      {services.length === 0 ? (
        <p className="rounded-lg border border-border bg-background/40 p-3 text-xs text-muted-foreground">
          {t("analyze.services.empty")}
        </p>
      ) : (
        <div className="flex max-h-44 flex-col gap-1.5 overflow-y-auto pr-1">
          {services.map((svc) => {
            const checked = selected.has(svc.id);
            return (
              <label
                key={svc.id}
                className={cn(
                  "flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 text-sm transition-colors",
                  checked
                    ? "border-primary/50 bg-primary/5"
                    : "border-border bg-background/40 hover:border-border"
                )}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => onToggle(svc.id)}
                  className="h-4 w-4 accent-primary"
                />
                <span className="flex-1 truncate font-medium">
                  {svc.name}
                </span>
                <Badge variant="muted">{t(`service.type.${svc.type}`)}</Badge>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}
