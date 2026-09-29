import {
  Shield,
  ScanSearch,
  Network,
  Languages,
  LayoutDashboard,
  LogIn,
  ShieldAlert,
} from "lucide-react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { cn } from "./lib/utils";
import { useI18n } from "./lib/i18n.jsx";
import { useAuth } from "./lib/auth.jsx";
import HealthIndicator from "./components/HealthIndicator";
import UserMenu from "./components/UserMenu";
import ProtectedRoute from "./components/ProtectedRoute";
import AnalysisPage from "./pages/AnalysisPage";
import ServicesPage from "./pages/ServicesPage";
import TaskDetailPage from "./pages/TaskDetailPage";
import DashboardPage from "./pages/DashboardPage";
import SensitiveDataPage from "./pages/SensitiveDataPage";
import LoginPage from "./pages/LoginPage";

const NAV = [
  { to: "/analysis", labelKey: "nav.analyze", icon: ScanSearch },
  { to: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/services", labelKey: "nav.services", icon: Network },
  { to: "/sensitive-data", labelKey: "nav.sensitive", icon: ShieldAlert },
];

export default function App() {
  const { t, lang, setLanguage } = useI18n();
  const { isAuthenticated } = useAuth();

  // Everything is gated behind login: only show the nav once authenticated.
  const navItems = isAuthenticated ? NAV : [];

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15">
              <Shield className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-lg font-semibold leading-tight">LiSA</h1>
              <p className="text-xs text-muted-foreground">{t("app.subtitle")}</p>
            </div>
          </div>

          <nav className="ml-auto flex items-center gap-1 rounded-lg bg-muted p-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-all",
                      isActive
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )
                  }
                >
                  <Icon className="h-4 w-4" />
                  {t(item.labelKey)}
                </NavLink>
              );
            })}
          </nav>

          <button
            type="button"
            onClick={() => setLanguage(lang === "en" ? "fr" : "en")}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            title="Switch language"
          >
            <Languages className="h-4 w-4" />
            {lang === "en" ? "FR" : "EN"}
          </button>

          {isAuthenticated ? (
            <UserMenu />
          ) : (
            <NavLink
              to="/login"
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              <LogIn className="h-4 w-4" />
              {t("auth.login")}
            </NavLink>
          )}

          <HealthIndicator />
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        <Routes>
          <Route path="/" element={<Navigate to="/analysis" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/analysis"
            element={
              <ProtectedRoute>
                <AnalysisPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/analysis/:taskId"
            element={
              <ProtectedRoute>
                <TaskDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/services"
            element={
              <ProtectedRoute>
                <ServicesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/sensitive-data"
            element={
              <ProtectedRoute>
                <SensitiveDataPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/analysis" replace />} />
        </Routes>
      </main>
    </div>
  );
}
