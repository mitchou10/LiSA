"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Set default environment variables for tests."""
    monkeypatch.setenv("GLINER_MODEL", "test-model")
    monkeypatch.setenv("GLINER_THRESHOLD", "0.5")
    monkeypatch.setenv("GLINER_LABELS", "person,email address,password,API key")
    monkeypatch.setenv("CELERY_QUEUE", "test-queue")
    # Unit tests never call the backend or Redis; they use the env defaults.
    monkeypatch.setenv("GLINER_PROFILE_ENABLED", "false")


@pytest.fixture
def mock_gliner_model(mocker):
    """Mock the GLiNER model to avoid downloading during tests."""
    model = MagicMock()
    mocker.patch("gliner.GLiNER.from_pretrained", return_value=model)
    return model


@pytest.fixture
def sample_input_single_string():
    """Sample input as a simple string."""
    return "My name is John Doe and my email is john@example.com"


@pytest.fixture
def sample_input_dict_with_content():
    """Sample input as dict with content field."""
    return {
        "content": "Contact me at jane@example.com",
    }


@pytest.fixture
def sample_input_dict_with_pages():
    """Sample input as dict with pages array."""
    return {
        "pages": [
            {
                "content": "Page 1: John Doe lives at 123 Main St",
                "page_number": 1,
            },
            {
                "content": "Page 2: Emergency contact: jane@example.com",
                "page_number": 2,
            },
        ]
    }


@pytest.fixture
def sample_gliner_entities():
    """Sample GLiNER model output."""
    return [
        {
            "text": "John Doe",
            "label": "person",
            "start": 11,
            "end": 20,
            "score": 0.95,
        },
        {
            "text": "john@example.com",
            "label": "email address",
            "start": 37,
            "end": 53,
            "score": 0.98,
        },
    ]


@pytest.fixture
def sample_gliner_entities_with_secrets():
    """Sample GLiNER output with secret entities."""
    return [
        {
            "text": "sk-1234567890abcdef",
            "label": "API key",
            "start": 10,
            "end": 28,
            "score": 0.99,
        },
        {
            "text": "myP@ssw0rd",
            "label": "password",
            "start": 50,
            "end": 60,
            "score": 0.85,
        },
    ]
