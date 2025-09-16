from abc import ABC, abstractmethod
from typing import TypeVar, Generic
import sys

from loguru import logger


logger.remove()
logger.add(sys.stdout, level="INFO")

T = TypeVar("T")
OutputType = TypeVar("OutputType")


class BaseInferenceModel(ABC, Generic[T, OutputType]):
    def __init__(self, model_name: str):
        self.model_name = model_name
        logger.info(f"Model {self.model_name} initialized.")

    @abstractmethod
    def predict(self, input_data: T) -> OutputType:
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def batch_predict(self, input_data_list: list[T]) -> list[OutputType]:
        raise NotImplementedError("Subclasses should implement this method.")
