import time
from transformers import pipeline
from worker.models.base import BaseInferenceModel
from worker.schemas.output import SingleAnalyserOutputSchema, BatchAnalyserOutputSchema
from worker.schemas.input import SingleAnalyserInputSchema, BatchAnalyserInputSchema


class ZeroShotModel(
    BaseInferenceModel[
        SingleAnalyserInputSchema,
        BatchAnalyserInputSchema,
        SingleAnalyserOutputSchema,
        BatchAnalyserOutputSchema,
    ]
):
    def __init__(self):
        super().__init__("zero-shot-classification")
        self.classifier = pipeline(
            "zero-shot-classification", model="facebook/bart-large-mnli"
        )

    def predict(self, input_data: dict) -> dict:
        try:
            input_data: SingleAnalyserInputSchema = (
                SingleAnalyserInputSchema.model_validate(input_data)
            )
        except Exception as e:
            raise ValueError(f"Invalid input data: {e}")
        t = time.time()
        result = SingleAnalyserOutputSchema(
            content=input_data.content, predictions={}, process_time=0.0
        )

        text = input_data.content
        candidate_labels = input_data.candidate_labels or [
            "santé",
            "finance",
            "éducation",
            "cybersécurité",
        ]

        prediction = self.classifier(
            text,
            candidate_labels=candidate_labels,
            multi_label=True,
        )
        result.process_time = time.time() - t
        result.predictions = dict(zip(prediction["labels"], prediction["scores"]))

        return result.model_dump()

    def batch_predict(self, input_data_list: dict) -> dict:
        try:
            input_data_list: BatchAnalyserInputSchema = (
                BatchAnalyserInputSchema.model_validate(input_data_list)
            )
        except Exception as e:
            raise ValueError(f"Invalid input data: {e}")
        t = time.time()
        candidate_labels = input_data_list.candidate_labels or [
            "santé",
            "finance",
            "éducation",
            "cybersécurité",
        ]
        texts = input_data_list.content

        output = BatchAnalyserOutputSchema(process_time=0.0, metadata={}, results=[])
        predictions = self.classifier(
            texts,
            candidate_labels=candidate_labels,
            multi_label=True,
        )
        output.process_time = time.time() - t
        for pred in predictions:
            result = SingleAnalyserOutputSchema(
                content=pred["sequence"],
                predictions=dict(zip(pred["labels"], pred["scores"])),
                process_time=output.process_time / len(texts),
            )
            output.results.append(result)

        return output.model_dump()

    def run(self, input_data: dict) -> dict:
        if self._is_valid_schema(
            data=input_data, schema_class=SingleAnalyserInputSchema
        ):
            return self.predict(input_data)
        elif self._is_valid_schema(
            data=input_data, schema_class=BatchAnalyserInputSchema
        ):
            return self.batch_predict(input_data)
        else:
            raise ValueError("Invalid input data format.")
