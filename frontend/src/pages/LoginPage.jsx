import { Navigate, useLocation } from "react-router-dom";
import {
  ArrowRight,
  Check,
  EyeOff,
  FileSearch,
  FileText,
  FolderKanban,
  KeyRound,
  Layers,
  LogIn,
  Network,
  ScanEye,
  Server,
  ShieldAlert,
  Shield,
  Tags,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { oidcLoginUrl } from "../lib/api";
import { useAuth } from "../lib/auth.jsx";
import { useI18n } from "../lib/i18n.jsx";
import resultsImg from "../assets/landing/results.png";
import projectImg from "../assets/landing/project.png";
import progressImg from "../assets/landing/progress.png";

const FEATURES = [
  { key: "pii", icon: ScanEye },
  { key: "relations", icon: Network },
  { key: "classification", icon: Tags },
  { key: "safety", icon: ShieldAlert },
  { key: "documents", icon: FileSearch },
  { key: "blur", icon: EyeOff },
];

const STEPS = ["source", "analysis", "run", "results"];

const TRUST = [
  { key: "sso", icon: KeyRound },
  { key: "projects", icon: FolderKanban },
  { key: "history", icon: Layers },
  { key: "selfhosted", icon: Server },
];

// A screenshot in a window frame.
function Shot({ src, alt, className = "" }) {
  return (
    <div className={`overflow-hidden rounded-xl border border-border bg-card shadow-2xl shadow-black/40 ${className}`}>
      <div className="flex items-center gap-1.5 border-b border-border bg-muted/60 px-3 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-destructive/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-success/70" />
      </div>
      <img src={src} alt={alt} loading="lazy" className="block w-full" />
    </div>
  );
}

// Sign-in happens on Keycloak: the backend runs the OIDC flow and brings the
// browser back here with a session cookie.
export default function LoginPage() {
  const { t } = useI18n();
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  const from = location.state?.from?.pathname || "/dashboard";
  const signIn = () => {
    window.location.href = oidcLoginUrl(from);
  };

  if (isAuthenticated) return <Navigate to={from} replace />;

  return (
    <div className="space-y-24 pb-12">
      {/* Hero */}
      <section className="grid items-center gap-10 pt-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <div className="space-y-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Shield className="h-3.5 w-3.5" />
            {t("landing.badge")}
          </span>
          <h2 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
            {t("landing.title.a")} <span className="text-primary">{t("landing.title.b")}</span>
          </h2>
          <p className="max-w-xl text-lg text-muted-foreground">{t("landing.subtitle")}</p>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="lg" onClick={signIn}>
              <LogIn className="h-4 w-4" />
              {t("auth.submit")}
            </Button>
            <a
              href="#features"
              className="inline-flex h-11 items-center gap-2 rounded-md px-4 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {t("landing.cta.more")}
              <ArrowRight className="h-4 w-4" />
            </a>
          </div>
          <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-muted-foreground">
            {["pdf", "images", "text"].map((k) => (
              <li key={k} className="flex items-center gap-1.5">
                <Check className="h-4 w-4 text-success" />
                {t(`landing.formats.${k}`)}
              </li>
            ))}
          </ul>
        </div>
        <Shot src={resultsImg} alt={t("landing.shot.results")} />
      </section>

      {/* Capabilities */}
      <section id="features" className="scroll-mt-8 space-y-8">
        <div className="max-w-2xl space-y-2">
          <h3 className="text-3xl font-bold tracking-tight">{t("landing.features.title")}</h3>
          <p className="text-muted-foreground">{t("landing.features.desc")}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ key, icon: Icon }) => (
            <div key={key} className="rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/40">
              <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 text-primary">
                <Icon className="h-5 w-5" />
              </span>
              <h4 className="font-semibold">{t(`landing.feature.${key}`)}</h4>
              <p className="mt-1.5 text-sm text-muted-foreground">{t(`landing.feature.${key}.desc`)}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="space-y-8">
        <div className="max-w-2xl space-y-2">
          <h3 className="text-3xl font-bold tracking-tight">{t("landing.how.title")}</h3>
          <p className="text-muted-foreground">{t("landing.how.desc")}</p>
        </div>
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((key, i) => (
            <li key={key} className="relative rounded-xl border border-border bg-card p-5">
              <span className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                {i + 1}
              </span>
              <h4 className="font-semibold">{t(`landing.step.${key}`)}</h4>
              <p className="mt-1.5 text-sm text-muted-foreground">{t(`landing.step.${key}.desc`)}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Product tour */}
      <section className="space-y-16">
        <div className="grid items-center gap-8 lg:grid-cols-2">
          <div className="space-y-3">
            <span className="inline-flex items-center gap-2 text-sm font-medium text-primary">
              <FolderKanban className="h-4 w-4" />
              {t("landing.tour.project.kicker")}
            </span>
            <h3 className="text-2xl font-bold tracking-tight">{t("landing.tour.project.title")}</h3>
            <p className="text-muted-foreground">{t("landing.tour.project.desc")}</p>
          </div>
          <Shot src={projectImg} alt={t("landing.shot.project")} />
        </div>
        <div className="grid items-center gap-8 lg:grid-cols-2">
          <Shot src={progressImg} alt={t("landing.shot.progress")} className="lg:order-first" />
          <div className="space-y-3 lg:order-last">
            <span className="inline-flex items-center gap-2 text-sm font-medium text-primary">
              <FileText className="h-4 w-4" />
              {t("landing.tour.run.kicker")}
            </span>
            <h3 className="text-2xl font-bold tracking-tight">{t("landing.tour.run.title")}</h3>
            <p className="text-muted-foreground">{t("landing.tour.run.desc")}</p>
          </div>
        </div>
      </section>

      {/* Trust */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {TRUST.map(({ key, icon: Icon }) => (
          <div key={key} className="flex gap-3 rounded-xl border border-border p-4">
            <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <div>
              <h4 className="text-sm font-semibold">{t(`landing.trust.${key}`)}</h4>
              <p className="mt-0.5 text-sm text-muted-foreground">{t(`landing.trust.${key}.desc`)}</p>
            </div>
          </div>
        ))}
      </section>

      {/* Final call to action */}
      <section className="rounded-2xl border border-primary/30 bg-primary/10 px-6 py-12 text-center">
        <h3 className="text-3xl font-bold tracking-tight">{t("landing.final.title")}</h3>
        <p className="mx-auto mt-2 max-w-xl text-muted-foreground">{t("landing.final.desc")}</p>
        <Button size="lg" className="mt-6" onClick={signIn}>
          <LogIn className="h-4 w-4" />
          {t("auth.submit")}
        </Button>
      </section>
    </div>
  );
}
