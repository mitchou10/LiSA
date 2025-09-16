import sys

from worker.models.analyser import ZeroShotModel
from worker.schemas.output import SingleAnalyserOutputSchema, BatchAnalyserOutputSchema
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO")


def test_analyser_model():
    analyser = ZeroShotModel(candidate_labels=["safe", "unsafe", "personal_data"])

    # Test single prediction
    result = analyser.predict("This is a test prompt.")
    logger.info(f"Single prediction result: {result}")
    assert SingleAnalyserOutputSchema.model_validate(result)

    # Test batch prediction
    inputs = [
        "This is the first test prompt.",
        "Here is another prompt for testing.",
        "This prompt is safe and contains no issues.",
        "Je m'appelle Jean Dupont et j'habite à Paris.",
    ]
    results = analyser.batch_predict(inputs)
    logger.info(f"Batch prediction results: {results}")
    result = BatchAnalyserOutputSchema.model_validate(results)
    assert result
    assert len(result.results) == 4
