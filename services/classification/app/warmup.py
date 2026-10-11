"""Download the model at image build time, so the worker starts offline-ready."""

from __future__ import annotations

from app.classifiers import get_classifier

if __name__ == "__main__":
    classifier = get_classifier()
    # Loading happens on the first call; any tiny task triggers it.
    from app.schemas import ClassificationTask

    classifier.classify("warmup", ClassificationTask(name="warmup", labels=["a", "b"]))
    print(f"Model ready: {classifier.name}")
