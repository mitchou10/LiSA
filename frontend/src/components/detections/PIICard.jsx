import { UserRound } from "lucide-react";
import { Badge } from "../ui/badge";
import DetectionCard from "./DetectionCard";
import { useI18n } from "../../lib/i18n.jsx";

export default function PIICard({ detection }) {
  const { t } = useI18n();
  const entities = detection.entities ?? [];
  return (
    <DetectionCard titleKey="detection.pii" icon={UserRound} detection={detection}>
      {entities.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs text-muted-foreground">
            {t("detection.entities")}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {entities.map((e) => (
              <Badge key={`${e.id ?? e.type}-${e.start_char ?? e}`} variant="muted">
                {e.type ?? e}
                {e.text ? ` : ${e.text}` : ""}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </DetectionCard>
  );
}
