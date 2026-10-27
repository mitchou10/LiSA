import { Check } from "lucide-react";
import { cn } from "../../../lib/utils";

/**
 * The steps of the analysis, numbered. A step already reached is a button
 * (when `canGo`, from step `from` on), the current one is highlighted, the
 * others wait.
 */
export default function Stepper({ steps, current, reached, canGo, onGo, from = 0 }) {
  return (
    <ol className="flex items-center gap-2" aria-label="Progress">
      {steps.map((label, i) => {
        const done = i < current;
        const active = i === current;
        const clickable = canGo && i >= from && i <= reached && !active;
        return (
          <li key={label} className="flex flex-1 items-center gap-2 last:flex-none">
            <button
              type="button"
              disabled={!clickable}
              onClick={() => onGo(i)}
              aria-current={active ? "step" : undefined}
              className={cn(
                "flex items-center gap-2 rounded-full py-1 pl-1 pr-3 text-sm font-medium transition-colors",
                active && "bg-primary/15 text-foreground",
                !active && "text-muted-foreground",
                clickable && "hover:text-foreground"
              )}
            >
              <span
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs",
                  active && "border-primary bg-primary text-primary-foreground",
                  done && "border-success bg-success/15 text-success",
                  !active && !done && "border-border"
                )}
              >
                {done ? <Check className="h-4 w-4" /> : i + 1}
              </span>
              <span className="hidden sm:inline">{label}</span>
            </button>
            {i < steps.length - 1 && (
              <span className={cn("h-px flex-1", done ? "bg-success/50" : "bg-border")} />
            )}
          </li>
        );
      })}
    </ol>
  );
}
