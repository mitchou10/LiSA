import { KeyRound } from "lucide-react";
import DetectionCard from "./DetectionCard";

export default function SecretLeakCard({ detection }) {
  return (
    <DetectionCard
      titleKey="detection.secret_leak"
      icon={KeyRound}
      detection={detection}
    />
  );
}
