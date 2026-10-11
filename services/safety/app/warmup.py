"""Download the model at image build time, so the worker starts offline-ready."""

from __future__ import annotations

from app.defaults import DEFAULT_PII_LABELS, DEFAULT_SAFETY_TASKS
from app.guards import get_guard

if __name__ == "__main__":
    guard = get_guard()
    guard.analyse("warmup", DEFAULT_PII_LABELS[:1], DEFAULT_SAFETY_TASKS[:1])
    print(f"Model ready: {guard.name}")
