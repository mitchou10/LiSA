import { Code2 } from "lucide-react";
import DetectionCard from "./DetectionCard";

export default function MaliciousCodeCard({ detection }) {
  return (
    <DetectionCard
      titleKey="detection.malicious_code"
      icon={Code2}
      detection={detection}
    />
  );
}
