from worker.models.base import BaseInferenceModel
from typing import Union


def test_base_worker():
    class DummyModel(BaseInferenceModel[str, list[str], str, list[str]]):
        def __init__(self):
            super().__init__("dummy-model")

        def predict(self, input_data: str) -> str:
            return "dummy-output"

        def batch_predict(self, input_data_list: list[str]) -> list[str]:
            return ["dummy-output" for _ in input_data_list]

        def run(self, input_data: Union[str, list[str]]) -> Union[str, list[str]]:
            if isinstance(input_data, str):
                return self.predict(input_data)
            elif isinstance(input_data, list):
                return self.batch_predict(input_data)
            raise ValueError("Invalid input data type.")

    worker = DummyModel()

    assert worker.predict("dummy-input") == "dummy-output"
    assert worker.batch_predict(["dummy-input-1", "dummy-input-2"]) == [
        "dummy-output",
        "dummy-output",
    ]

    assert worker.run("dummy-input") == "dummy-output"
    assert worker.run(["dummy-input-1", "dummy-input-2"]) == [
        "dummy-output",
        "dummy-output",
    ]
