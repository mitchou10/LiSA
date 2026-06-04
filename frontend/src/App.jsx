import { useState } from "react";
import { Shield, ScanSearch, Network } from "lucide-react";
import { cn } from "./lib/utils";
import AnalyzePage from "./pages/AnalyzePage";
import ServicesPage from "./pages/ServicesPage";

const NAV = [
  { id: "analyze", label: "Analyse", icon: ScanSearch },
  { id: "services", label: "Services & Tâches", icon: Network },
];

export default function App() {
  const [page, setPage] = useState("analyze");

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
              <p className="text-xs text-muted-foreground">
                Détection de jailbreak, prompt injection &amp; supervision
              </p>
            </div>
          </div>

          <nav className="ml-auto flex items-center gap-1 rounded-lg bg-muted p-1">
            {NAV.map((item) => {
              const Icon = item.icon;
              const active = page === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setPage(item.id)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-all",
                    active
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {page === "analyze" ? <AnalyzePage /> : <ServicesPage />}
      </main>
    </div>
  );
}
