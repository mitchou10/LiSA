import json
import os
from typing import Union
from pydantic import BaseModel, Field


class InputSchema(BaseModel):
    """
    Schema for input data validation.
    """

    text: Union[str, list[str]] = Field(
        ..., description="The input text to be processed."
    )
    extras: dict = Field(
        default_factory=dict, description="Additional parameters for processing."
    )


s = InputSchema.model_json_schema(
    ref_template="#/components/schemas/{model}", mode="serialization"
)

# Get the project root (LiSA directory)
current_dir = os.path.dirname(__file__)  # schemas folder
project_root = os.path.abspath(os.path.join(current_dir, "../../../../"))
DEFAULT_CONFIG_SCHEMA_FOLDER = os.environ.get(
    "DEFAULT_CONFIG_SCHEMA_FOLDER",
    os.path.join(project_root, "worker", "configs", "schemas"),
)


SERVICE_NAME = os.environ.get("SERVICE_NAME", "lisa")


with open(
    os.path.join(DEFAULT_CONFIG_SCHEMA_FOLDER, f"{SERVICE_NAME}.json"),
    "w",
    encoding="utf-8",
) as f:
    json.dump(s, f, ensure_ascii=False, indent=4)
