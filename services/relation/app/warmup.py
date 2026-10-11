"""Download the model at image build time, so the worker starts offline-ready."""

from __future__ import annotations

from app.extractors import get_extractor
from app.schemas import RelationRule

if __name__ == "__main__":
    extractor = get_extractor()
    extractor.extract("warmup", [RelationRule(name="works_for")], 0.5)
    print(f"Model ready: {extractor.name}")
