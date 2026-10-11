"""Download the model at image build time, so the worker starts offline-ready."""

from __future__ import annotations

from app.extractors import get_extractor
from app.schemas import EntityRule

if __name__ == "__main__":
    extractor = get_extractor()
    extractor.extract("warmup", [EntityRule(label="person")], 0.5)
    print(f"Model ready: {extractor.name}")
