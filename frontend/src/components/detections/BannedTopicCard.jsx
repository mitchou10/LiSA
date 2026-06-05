import { Ban } from "lucide-react";
import { Badge } from "../ui/badge";
import DetectionCard from "./DetectionCard";
import { useI18n } from "../../lib/i18n.jsx";

export default function BannedTopicCard({ detection }) {
  const { t } = useI18n();
  const topics = detection.topics ?? [];
  return (
    <DetectionCard
      titleKey="detection.banned_topic"
      icon={Ban}
      detection={detection}
    >
      {topics.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs text-muted-foreground">
            {t("detection.topics")}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {topics.map((topic) => (
              <Badge key={topic} variant="muted">
                {topic}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </DetectionCard>
  );
}
