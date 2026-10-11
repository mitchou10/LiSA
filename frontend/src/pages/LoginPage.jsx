import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Shield, Loader2, LogIn } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { useAuth } from "../lib/auth.jsx";
import { oidcLoginUrl } from "../lib/api";
import { useI18n } from "../lib/i18n.jsx";

export default function LoginPage() {
  const { t } = useI18n();
  const { signIn, provider } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const from = location.state?.from?.pathname || "/dashboard";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signIn(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err?.status === 401 ? t("auth.error") : err?.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/15">
            <Shield className="h-6 w-6 text-primary" />
          </div>
          <CardTitle>{t("auth.title")}</CardTitle>
          <CardDescription>{t("auth.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          {provider === "keycloak" ? (
            <Button
              className="w-full"
              onClick={() => {
                window.location.href = oidcLoginUrl(from);
              }}
            >
              <LogIn className="h-4 w-4" />
              {t("auth.submit")}
            </Button>
          ) : (
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="username">
                {t("auth.username")}
              </label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={t("auth.username.placeholder")}
                autoComplete="username"
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="password">
                {t("auth.password")}
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t("auth.password.placeholder")}
                autoComplete="current-password"
                required
              />
            </div>

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LogIn className="h-4 w-4" />
              )}
              {loading ? t("auth.signingIn") : t("auth.submit")}
            </Button>
          </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
