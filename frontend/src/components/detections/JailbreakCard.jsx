import { Unlock } from "lucide-react";
import DetectionCard from "./DetectionCard";

export default function JailbreakCard({ detection }) {
  return (
    <DetectionCard
      titleKey="detection.jailbreak"
      icon={Unlock}
      detection={detection}
    />
  );
}
