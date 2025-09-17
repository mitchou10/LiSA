import pytest
from worker.main import LiSASyncTask
from async_worker.worker import IncomingMessage


def test_instantiate_lisa_sync_task_guard():
    from worker.models.guard import GuardModel

    task = LiSASyncTask(model_name="guard")
    assert isinstance(task, LiSASyncTask)
    assert isinstance(task.model, GuardModel)
    task.execute(
        incoming_message=IncomingMessage(
            task_id="test", body={"data": "This is a test"}
        ),
        progress=lambda x: x,
    )

    task.execute(
        incoming_message=IncomingMessage(
            task_id="test", body={"data": ["This is a test"]}
        ),
        progress=lambda x: x,
    )
    with pytest.raises(ValueError):
        task.execute(
            incoming_message=IncomingMessage(task_id="test", body={"data": 12345}),
            progress=lambda x: x,
        )


def test_instantiate_lisa_sync_task_analyser():
    from worker.models.analyser import ZeroShotModel

    task = LiSASyncTask(model_name="analyser")
    assert isinstance(task, LiSASyncTask)
    assert isinstance(task.model, ZeroShotModel)
    task.execute(
        incoming_message=IncomingMessage(
            task_id="test",
            body={
                "data": {
                    "content": "This is a test prompt.",
                    "candidate_labels": [
                        "santé",
                        "finance",
                        "éducation",
                        "cybersécurité",
                    ],
                }
            },
        ),
        progress=lambda x: x,
    )

    task.execute(
        incoming_message=IncomingMessage(
            task_id="test",
            body={
                "data": {
                    "content": ["This is a test prompt."],
                    "candidate_labels": [
                        "santé",
                        "finance",
                        "éducation",
                        "cybersécurité",
                    ],
                }
            },
        ),
        progress=lambda x: x,
    )
    with pytest.raises(ValueError):
        task.execute(
            incoming_message=IncomingMessage(task_id="test", body={"data": 12345}),
            progress=lambda x: x,
        )
