import { useLocation } from "react-router-dom";
import { Shield, LogIn } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { oidcLoginUrl } from "../lib/api";
import { useI18n } from "../lib/i18n.jsx";

// Sign-in happens on Keycloak: the backend runs the OIDC flow and brings the
// browser back here with a session cookie.
export default function LoginPage() {
  const { t } = useI18n();
  const location = useLocation();

  const from = location.state?.from?.pathname || "/dashboard";

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
          <Button
            className="w-full"
            onClick={() => {
              window.location.href = oidcLoginUrl(from);
            }}
          >
            <LogIn className="h-4 w-4" />
            {t("auth.submit")}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
