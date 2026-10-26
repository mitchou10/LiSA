import { cn } from "../../../lib/utils";

/** A large radio-like card: an icon, a title, a line of help. */
export default function OptionCard({ icon: Icon, title, desc, badge, selected, onSelect, children }) {
  return (
    <div
      className={cn(
        "rounded-xl border transition-colors",
        selected ? "border-primary bg-primary/5" : "border-border bg-background/40 hover:border-muted-foreground/40"
      )}
    >
      <button
        type="button"
        role="radio"
        aria-checked={selected}
        onClick={onSelect}
        className="flex w-full items-start gap-3 p-4 text-left"
      >
        <span
          className={cn(
            "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
            selected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
          )}
        >
          <Icon className="h-5 w-5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2 font-medium">
            {title}
            {badge && (
              <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs font-medium text-success">
                {badge}
              </span>
            )}
          </span>
          <span className="mt-0.5 block text-sm text-muted-foreground">{desc}</span>
        </span>
        <span
          className={cn(
            "mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border",
            selected ? "border-primary" : "border-border"
          )}
        >
          {selected && <span className="h-2.5 w-2.5 rounded-full bg-primary" />}
        </span>
      </button>
      {selected && children && <div className="border-t border-border/60 p-4">{children}</div>}
    </div>
  );
}
