from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Action(str, Enum):
    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


class DetectionResult(BaseModel):
    """Base fields shared by every detector result."""

    flagged: bool = Field(
        ..., description="Global verdict: True if the detector flagged the content."
    )
    confidence: float = Field(
        ..., description="Detector confidence in the verdict, between 0.0 and 1.0."
    )
    severity: Severity | None = Field(
        None, description="Risk level of the finding: low, medium or high."
    )
    action: Action | None = Field(
        None,
        description="Recommended action to apply: allow, redact or block.",
    )
    details: dict | None = Field(
        None,
        description="Free-form detector-specific metadata (matched spans, scores, etc.).",
    )
    service_id: str | None = Field(
        None, description="Identifier of the service/worker that produced this result."
    )


class JailbreakDetectionResult(DetectionResult):
    jailbreak: bool = Field(
        ..., description="True if a jailbreak attempt was detected in the prompt."
    )


class PromptInjectionDetectionResult(DetectionResult):
    prompt_injection: bool = Field(
        ..., description="True if a prompt injection attempt was detected."
    )


class SecretLeakDetectionResult(DetectionResult):
    secret_leak: bool = Field(
        ...,
        description="True if technical secrets (API keys, tokens, credentials) were found.",
    )


class SensitiveDataExposureDetectionResult(DetectionResult):
    sensitive_data_exposure: bool = Field(
        ...,
        description="True if confidential business data was exposed.",
    )


class ToxicityDetectionResult(DetectionResult):
    toxic: bool = Field(
        ...,
        description="True if toxic, hateful or offensive content was detected.",
    )


class Entity(DetectionResult):
    id: str = Field(..., description="Unique identifier of the detected entity.")
    type: str = Field(..., description="Type or category of the detected entity.")
    text: str = Field(..., description="Original text span of the detected entity.")
    start_char: int = Field(
        ..., description="Start character index of the entity in the input."
    )
    end_char: int = Field(
        ..., description="End character index of the entity in the input."
    )


class PIIDetectionResult(DetectionResult):
    """Personally identifiable information (RGPD): names, emails, IBAN, etc."""

    pii: bool = Field(
        ..., description="True if personally identifiable information was detected."
    )
    entities: list[Entity] | None = Field(
        None,
        description="List of detected PII entities.",
    )


class BannedTopicDetectionResult(DetectionResult):
    """Off-topic / forbidden subjects (e.g. competitors, restricted domains)."""

    banned_topic: bool = Field(
        ..., description="True if a forbidden or off-topic subject was detected."
    )
    topics: list[str] | None = Field(
        None, description="List of matched banned/off-topic subjects."
    )


class BiasDetectionResult(DetectionResult):
    bias: bool = Field(
        ..., description="True if biased or unfair content was detected."
    )


class HallucinationDetectionResult(DetectionResult):
    """Output factuality / grounding check."""

    hallucination: bool = Field(
        ...,
        description="True if the model output appears unfactual or ungrounded.",
    )


class MaliciousCodeDetectionResult(DetectionResult):
    malicious_code: bool = Field(
        ..., description="True if malicious or dangerous code was detected."
    )


class PageResult(BaseModel):
    page_number: int | None = Field(
        None,
        description="Page number for multi-page documents (null for single-page inputs).",
    )
    detections: list[DetectionResult] = Field(
        ..., description="List of detection results for this page."
    )


class Analyse(BaseModel):
    id: str = Field(..., description="Unique identifier of the analysis task.")
    pages: list[PageResult] = Field(
        ..., description="List of pages with their respective detection results."
    )

    error: str | None = Field(None, description="Error message if the analysis failed.")
