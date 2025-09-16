from worker.main import LiSASyncTask


def test_instantiate_lisa_sync_task_guard():
    from worker.models.guard import GuardModel

    task = LiSASyncTask(model_name="guard")
    assert isinstance(task, LiSASyncTask)
    assert isinstance(task.model, GuardModel)


def test_instantiate_lisa_sync_task_analyser():
    from worker.models.analyser import ZeroShotModel

    task = LiSASyncTask(model_name="analyser")
    assert isinstance(task, LiSASyncTask)
    assert isinstance(task.model, ZeroShotModel)
