import { Scale } from "lucide-react";
import DetectionCard from "./DetectionCard";

export default function BiasCard({ detection }) {
  return (
    <DetectionCard titleKey="detection.bias" icon={Scale} detection={detection} />
  );
}
