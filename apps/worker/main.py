import asyncio
import logging
import os
import sys
from collections.abc import Callable

from typing import Any, Literal

from loguru import logger

from async_worker import (
    AsyncWorkerRunner,
    HealthCheckConfig,
    IncomingMessage,
    Infinite,
    SyncTaskInterface,
)


# --------------------------------
# L'implementation du worker est indépendante du système de logging
# Dans notre exemple, nous voulons utiliser loguru, il nous faut donc
# intercepter les logs du module logging standard et les rediriger vers loguru
# --------------------------------
class InterceptHandler(logging.Handler):
    """Handler pour intercepter les logs du module logging standard et les rediriger vers loguru"""

    def emit(self, record: logging.LogRecord) -> None:  # noqa: PLR6301
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
logger.remove()
logger.add(sys.stdout, level="INFO")


class LiSASyncTask(SyncTaskInterface):
    def __init__(
        self,
        model_name: Literal["guard", "analyser"] = os.environ.get(
            "MODEL_NAME", "guard"
        ),
    ) -> None:
        super().__init__()
        if model_name not in ["guard", "analyser"]:
            raise ValueError(f"Unknown model name: {model_name}")

        self.model_name = model_name
        if model_name == "guard":
            from worker.models.guard import GuardModel

            self.model = GuardModel()
        elif model_name == "analyser":
            from worker.models.analyser import ZeroShotModel

            self.model = ZeroShotModel()
        else:
            raise NotImplementedError(
                "PersonalDataModelDetection is not implemented yet"
            )

    def execute(
        self, incoming_message: IncomingMessage, progress: Callable[[float], None]
    ) -> Any:  # noqa: ANN401 PLR6301
        task_id = incoming_message.task_id
        body: dict[Any, Any] = incoming_message.body
        logging.info(f"Task_id: {task_id}")
        progress(0.1)
        data = body.get("data")
        progress(1.0)
        return self.model.run(data)


OUT_QUEUE_NAME = os.environ.get("OUT_QUEUE_NAME", "example_out_queue")
IN_QUEUE_NAME = os.environ.get("IN_QUEUE_NAME", "in_queue_python")
BROKER_URL = os.environ.get("BROKER_URL", "")
WORKER_CONCURRENCY: int = int(os.environ.get("WORKER_CONCURRENCY", default="5"))
if not BROKER_URL:
    raise ValueError("BROKER_URL environment variable is not set.")


async def main() -> None:
    logger.info("Launch")
    runner = AsyncWorkerRunner(
        # Rabbit mq connection
        amqp_url=BROKER_URL,
        # In out queues
        amqp_in_queue=IN_QUEUE_NAME,
        amqp_out_queue=OUT_QUEUE_NAME,
        task_provider=LiSASyncTask,  # or  lambda:  MySyncTask()
        worker_mode=Infinite(concurrency=WORKER_CONCURRENCY),  # or OnShot(),
        # Optional : HealthCheck
        health_check_config=HealthCheckConfig(host="127.0.0.1", port=8000),  # or None
    )
    await runner.start()
    logger.info("Stopped.")


# Main
if __name__ == "__main__":
    asyncio.run(main())
