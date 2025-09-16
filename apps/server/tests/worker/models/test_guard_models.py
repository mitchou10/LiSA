import pytest
from worker.models.guard import GuardModel
from worker.schemas.output import SingleGuardOutputSchema, BatchGuardOutputSchema
from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, level="INFO")


def test_guard_model():
    guard = GuardModel()

    # Test single prediction
    result = guard.predict("This is a test prompt with a secret: my_password")
    logger.debug(f"Single prediction result: {result}")
    assert SingleGuardOutputSchema.model_validate(result)

    # Test batch prediction
    inputs = [
        "This is a safe prompt.",
        "This prompt contains a secret: api_key_12345",
        "Another safe prompt.",
        "Je m'appelle Jean Dupont et j'habite à Paris.",
    ]
    results = guard.batch_predict(inputs)
    result = BatchGuardOutputSchema.model_validate(results)
    assert result
    assert len(result.results) == 4

    with pytest.raises(ValueError):
        guard.batch_predict(["Valid string", 12345, "Another valid string"])  # type: ignore
