import { Database } from "lucide-react";
import DetectionCard from "./DetectionCard";

export default function SensitiveDataExposureCard({ detection }) {
  return (
    <DetectionCard
      titleKey="detection.sensitive_data_exposure"
      icon={Database}
      detection={detection}
    />
  );
}
