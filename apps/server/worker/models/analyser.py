import time
from transformers import pipeline
from worker.models.base import BaseInferenceModel
from worker.schemas.output import SingleAnalyserOutputSchema, BatchAnalyserOutputSchema


class ZeroShotModel(BaseInferenceModel[str, dict]):
    def __init__(self, candidate_labels: list[str]):
        super().__init__("zero-shot-classification")
        self.classifier = pipeline(
            "zero-shot-classification", model="facebook/bart-large-mnli"
        )
        self.candidate_labels = candidate_labels

    def predict(self, input_data: str) -> dict:

        t = time.time()
        result = SingleAnalyserOutputSchema(
            content=input_data, predictions={}, process_time=0.0
        )

        prediction = self.classifier(
            input_data, candidate_labels=self.candidate_labels, multi_label=True
        )
        result.process_time = time.time() - t
        result.predictions = dict(zip(prediction["labels"], prediction["scores"]))

        return result.model_dump()

    def batch_predict(self, input_data_list: list[str]) -> dict:
        # [{'sequence': 'This is the first test prompt.', 'labels': ['personal_data', 'safe', 'unsafe'], 'scores': [0.6744127869606018, 0.05009875074028969, 0.03015664964914322]}, {'sequence': 'Here is another prompt for testing.', 'labels': ['personal_data', 'unsafe', 'safe'], 'scores': [0.545461118221283, 0.011019181460142136, 0.004518075846135616]}, {'sequence': 'This prompt is safe and contains no issues.', 'labels': ['safe', 'personal_data', 'unsafe'], 'scores': [0.9941592812538147, 0.4689462184906006, 0.0008468754240311682]}, {'sequence': "Je m'appelle Jean Dupont et j'habite à Paris.", 'labels': ['safe', 'unsafe', 'personal_data'], 'scores': [0.12182316929101944, 0.10817234218120575, 0.04696241766214371]}]
        t = time.time()
        output = BatchAnalyserOutputSchema(process_time=0.0, metadata={}, results=[])
        predictions = self.classifier(
            input_data_list,
            candidate_labels=self.candidate_labels,
            multi_label=True,
        )
        output.process_time = time.time() - t
        for pred in predictions:
            result = SingleAnalyserOutputSchema(
                content=pred["sequence"],
                predictions=dict(zip(pred["labels"], pred["scores"])),
                process_time=output.process_time / len(input_data_list),
            )
            output.results.append(result)

        return output.model_dump()
