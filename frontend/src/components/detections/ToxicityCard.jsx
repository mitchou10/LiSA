import { Biohazard } from "lucide-react";
import DetectionCard from "./DetectionCard";

export default function ToxicityCard({ detection }) {
  return (
    <DetectionCard
      titleKey="detection.toxicity"
      icon={Biohazard}
      detection={detection}
    />
  );
}
