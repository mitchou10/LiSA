import { Ghost } from "lucide-react";
import DetectionCard from "./DetectionCard";

export default function HallucinationCard({ detection }) {
  return (
    <DetectionCard
      titleKey="detection.hallucination"
      icon={Ghost}
      detection={detection}
    />
  );
}
