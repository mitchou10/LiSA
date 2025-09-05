from worker.models.base import BaseInferenceModel
from llm_guard import scan_prompt
from llm_guard.input_scanners import PromptInjection, Secrets


class GuardModel(BaseInferenceModel[str, tuple[str, dict[str, float]]]):
    def __init__(self):
        super().__init__("llm-guard")
        self.input_scanners = [
            PromptInjection(threshold=0.8, use_onnx=False),
            Secrets(),
        ]

    def predict(self, input_data: str) -> dict:
        return scan_prompt(self.input_scanners, input_data)

    def batch_predict(self, input_data_list: list[str]) -> list[dict]:
        return [
            scan_prompt(self.input_scanners, input_data)
            for input_data in input_data_list
        ]


if __name__ == "__main__":
    guard = GuardModel()
    print(guard.predict("This is a test prompt with a secret: my_password"))
    print(
        guard.batch_predict(
            [
                "This is a safe prompt.",
                "This prompt contains a secret: api_key_12345",
                "Another safe prompt.",
                "Je m'appelle Jean Dupont et j'habite à Paris.",
            ]
        )
    )
