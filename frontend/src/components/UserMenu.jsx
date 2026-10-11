import { useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  ChevronDown,
  LayoutDashboard,
  LogOut,
  Network,
  ShieldAlert,
  ShieldCheck,
  UserCircle,
} from "lucide-react";
import { cn } from "../lib/utils";
import { useI18n } from "../lib/i18n.jsx";
import { useAuth } from "../lib/auth.jsx";

const MENU_LINKS = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/services", labelKey: "nav.services", icon: Network },
  { to: "/sensitive-data", labelKey: "nav.sensitive", icon: ShieldAlert },
];

export default function UserMenu() {
  const { t } = useI18n();
  const { user, isAdmin, signOut } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="inline-flex items-center gap-2 rounded-lg border border-border px-2.5 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-muted"
      >
        <UserCircle className="h-4 w-4 text-muted-foreground" />
        <span className="max-w-[10rem] truncate">{user?.username}</span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 text-muted-foreground transition-transform",
            open && "rotate-180"
          )}
        />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-lg border border-border bg-background shadow-lg"
        >
          <div className="border-b border-border px-3 py-2.5">
            <p className="truncate text-sm font-medium">{user?.username}</p>
            <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
              {isAdmin && <ShieldCheck className="h-3 w-3 text-primary" />}
              {isAdmin ? t("auth.role.admin") : t("auth.role.user")}
            </p>
          </div>

          <div className="border-b border-border py-1">
            {MENU_LINKS.map(({ to, labelKey, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                role="menuitem"
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-muted hover:text-foreground",
                    isActive ? "text-foreground" : "text-muted-foreground"
                  )
                }
              >
                <Icon className="h-4 w-4" />
                {t(labelKey)}
              </NavLink>
            ))}
          </div>

          <div className="py-1">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                signOut();
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <LogOut className="h-4 w-4" />
              {t("auth.logout")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
