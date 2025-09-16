import time
from worker.models.base import BaseInferenceModel
from worker.schemas.output import SingleGuardOutputSchema, BatchGuardOutputSchema
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
        t = time.time()
        result: tuple[str, dict[str, bool], dict[str, float]] = scan_prompt(
            self.input_scanners, input_data
        )
        process_time = time.time() - t
        content, predictions, scores = result
        output_schema = SingleGuardOutputSchema(
            process_time=process_time,
            metadata={},
            content=content,
            predictions=predictions,
            scores=scores,
        )
        return output_schema.model_dump()

    def batch_predict(self, input_data_list: list[str]) -> dict:
        t = time.time()
        output_schema = BatchGuardOutputSchema(
            process_time=0.0, metadata={}, results=[]
        )
        for item in input_data_list:
            if not isinstance(item, str):
                raise ValueError("All items in input_data_list must be strings.")
            result = self.predict(item)  # Validate each item
            output_schema.results.append(SingleGuardOutputSchema(**result))

        output_schema.process_time = time.time() - t
        return output_schema.model_dump()
