from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Union, Type
from pydantic import BaseModel
import sys

from loguru import logger


logger.remove()
logger.add(sys.stdout, level="INFO")

SingleInputType = TypeVar("SingleInputType")
BatchInputType = TypeVar("BatchInputType")
OutputType = TypeVar("OutputType")
BatchOutputType = TypeVar("BatchOutputType")


class BaseInferenceModel(
    ABC, Generic[SingleInputType, BatchInputType, OutputType, BatchOutputType]
):
    def __init__(self, model_name: str):
        self.model_name = model_name
        logger.info(f"Model {self.model_name} initialized.")

    @abstractmethod
    def predict(self, input_data: SingleInputType) -> OutputType:
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def batch_predict(self, input_data_list: BatchInputType) -> BatchOutputType:
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def run(
        self, input_data: Union[SingleInputType, BatchInputType]
    ) -> Union[OutputType, BatchOutputType]:
        raise NotImplementedError("Subclasses should implement this method.")

    def _is_valid_schema(
        self, data: dict, schema_class: Type[Union[BaseModel, TypeVar]]
    ) -> bool:
        if not issubclass(schema_class, BaseModel):
            return isinstance(data, schema_class)
        try:
            schema_class.model_validate(data)
            return True
        except Exception as e:
            logger.error(f"Schema validation error: {e}")
            return False
