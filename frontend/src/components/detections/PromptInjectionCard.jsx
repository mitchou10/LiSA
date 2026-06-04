import { Syringe } from "lucide-react";
import DetectionCard from "./DetectionCard";

export default function PromptInjectionCard({ detection }) {
  return (
    <DetectionCard
      titleKey="detection.prompt_injection"
      icon={Syringe}
      detection={detection}
    />
  );
}
