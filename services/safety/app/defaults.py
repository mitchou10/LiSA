"""What is checked when the input does not say: PII types and safety tasks.

Safety tasks and labels follow the GLiNER2 guardrails tutorial.
"""

from __future__ import annotations

from app.schemas import Label, SafetyTask

# A subset of the 42 PII types of the checkpoint: every label costs model
# context, so only the commonly redacted ones are on by default.
DEFAULT_PII_LABELS = [
    Label(name="person", description="A person's name"),
    Label(name="email", description="An e-mail address"),
    Label(name="phone_number", description="A telephone number"),
    Label(name="address", description="A postal address"),
    Label(name="date_of_birth", description="A person's date of birth"),
    Label(name="government_id", description="A national identity number"),
    Label(name="passport_number", description="A passport number"),
    Label(name="tax_id", description="A tax identification number"),
    Label(name="iban", description="An IBAN bank account number"),
    Label(name="payment_card", description="A payment card number"),
    Label(name="ip_address", description="An IP address"),
    Label(name="password", description="A password"),
    Label(name="api_key", description="An API key"),
    Label(name="access_token", description="An access token"),
    Label(name="secret", description="A secret or credential"),
]

DEFAULT_SAFETY_TASKS = [
    SafetyTask(
        name="prompt_safety",
        labels=["safe", "unsafe"],
        ok_labels=["safe"],
    ),
    SafetyTask(
        name="jailbreak_detection",
        multi_label=True,
        labels=[
            "prompt_injection",
            "jailbreak_attempt",
            "policy_evasion",
            "instruction_override",
            "system_prompt_exfiltration",
            "data_exfiltration",
            "roleplay_bypass",
            "hypothetical_bypass",
            "obfuscated_attack",
            "multi_step_attack",
            "social_engineering",
            "benign",
        ],
        ok_labels=["benign"],
    ),
    SafetyTask(
        name="prompt_toxicity",
        multi_label=True,
        labels=[
            "violence_and_weapons",
            "non_violent_crime",
            "sexual_content",
            "hate_and_discrimination",
            "self_harm_and_suicide",
            "child_safety",
            "misinformation",
            "unethical_conduct",
            "benign",
        ],
        ok_labels=["benign"],
    ),
]
