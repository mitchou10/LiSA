"""Download the model at image build time, so the worker starts offline-ready."""

from __future__ import annotations

from PIL import Image

from app.classifiers import get_classifier
from app.schemas import ClassificationTask

if __name__ == "__main__":
    classifier = get_classifier()
    task = ClassificationTask(name="warmup", labels=["a cat", "a dog"])
    classifier.classify(Image.new("RGB", (32, 32), "white"), task)
    print(f"Model ready: {classifier.name}")
