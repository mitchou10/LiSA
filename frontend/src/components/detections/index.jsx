import { ShieldQuestion } from "lucide-react";
import DetectionCard from "./DetectionCard";
import JailbreakCard from "./JailbreakCard";
import PromptInjectionCard from "./PromptInjectionCard";
import SecretLeakCard from "./SecretLeakCard";
import SensitiveDataExposureCard from "./SensitiveDataExposureCard";
import ToxicityCard from "./ToxicityCard";
import PIICard from "./PIICard";
import BannedTopicCard from "./BannedTopicCard";
import BiasCard from "./BiasCard";
import HallucinationCard from "./HallucinationCard";
import MaliciousCodeCard from "./MaliciousCodeCard";

// Maps a detection `type` to its dedicated card component.
export const DETECTION_CARDS = {
  jailbreak: JailbreakCard,
  prompt_injection: PromptInjectionCard,
  secret_leak: SecretLeakCard,
  sensitive_data_exposure: SensitiveDataExposureCard,
  toxicity: ToxicityCard,
  pii: PIICard,
  banned_topic: BannedTopicCard,
  bias: BiasCard,
  hallucination: HallucinationCard,
  malicious_code: MaliciousCodeCard,
};

/** Fallback card for unknown detection types. */
function UnknownCard({ detection }) {
  return (
    <DetectionCard
      titleKey="detection.unknown"
      icon={ShieldQuestion}
      detection={detection}
    />
  );
}

export function DetectionCardFor({ detection }) {
  const Card = DETECTION_CARDS[detection.type] ?? UnknownCard;
  return <Card detection={detection} />;
}
