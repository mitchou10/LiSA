from worker.models.base import BaseInferenceModel


def test_base_worker():
    class DummyModel(BaseInferenceModel[str, str]):
        def __init__(self):
            super().__init__("dummy-model")

        def predict(self, input_data: str) -> str:
            return "dummy-output"

        def batch_predict(self, input_data_list: list[str]) -> list[str]:
            return ["dummy-output" for _ in input_data_list]

    worker = DummyModel()

    assert worker.predict("dummy-input") == "dummy-output"
    assert worker.batch_predict(["dummy-input-1", "dummy-input-2"]) == [
        "dummy-output",
        "dummy-output",
    ]
