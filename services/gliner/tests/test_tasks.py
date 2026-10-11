"""Tests for Celery tasks."""

from __future__ import annotations

import pytest
from app.tasks import get_service, scan


class TestGetService:
    """Tests for get_service() singleton."""

    def test_get_service_returns_gliner_service(self, mock_env):
        service = get_service()
        assert service is not None
        assert service.__class__.__name__ == "GlinerService"

    def test_get_service_caches_singleton(self, mock_env):
        service1 = get_service()
        service2 = get_service()
        assert service1 is service2  # Same instance (cached via lru_cache)

    def test_get_service_cache_maxsize(self, mock_env):
        # Cache maxsize is 1, so only one instance is kept
        assert get_service.cache_info().maxsize == 1

    def test_get_service_cache_hits(self, mock_env):
        get_service.cache_clear()
        get_service()
        info = get_service.cache_info()
        assert info.hits == 0  # First call is a miss
        assert info.misses == 1

        get_service()
        info = get_service.cache_info()
        assert info.hits == 1  # Second call is a hit
        assert info.misses == 1


class TestScanTask:
    """Tests for the scan() Celery task."""

    def test_scan_task_calls_service_process(self, mock_env, mock_gliner_model):
        mock_gliner_model.predict_entities.return_value = []

        result = scan("test content", task_id="task-123")

        assert result["id"] == "task-123"
        assert result["error"] is None
        assert len(result["pages"]) == 1

    def test_scan_task_with_dict_input(self, mock_env, mock_gliner_model):
        mock_gliner_model.predict_entities.return_value = []

        input_data = {"content": "test content"}
        result = scan(input_data, task_id="task-456")

        assert result["id"] == "task-456"
        assert len(result["pages"]) == 1

    def test_scan_task_without_task_id(self, mock_env, mock_gliner_model):
        mock_gliner_model.predict_entities.return_value = []

        result = scan("test content")

        assert result["id"].startswith("gliner-")
        assert result["error"] is None

    def test_scan_task_returns_detection_results(self, mock_env, mock_gliner_model):
        entities = [
            {
                "text": "sensitive",
                "label": "person",
                "start": 0,
                "end": 9,
                "score": 0.9,
            }
        ]
        mock_gliner_model.predict_entities.return_value = entities

        result = scan("sensitive data here", task_id="detection-task")

        assert result["pages"][0]["detections"][0]["flagged"] is True
        assert len(result["pages"][0]["detections"][0]["entities"]) == 1

    def test_scan_task_propagates_exceptions(self, mock_env, mock_gliner_model):
        mock_gliner_model.predict_entities.side_effect = ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            scan("test content", task_id="error-task")

    def test_scan_task_singleton_reuse(self, mock_env, mock_gliner_model):
        """Verify that multiple scan calls reuse the same service instance."""
        mock_gliner_model.predict_entities.return_value = []

        get_service.cache_clear()

        scan("content 1", task_id="task-1")
        scan("content 2", task_id="task-2")

        # Both calls should use the same cached service instance
        info = get_service.cache_info()
        assert info.misses == 1  # Only first call was a miss
        assert info.hits == 1  # Second call was a hit


class TestScanTaskIntegration:
    """Integration tests for scan task with realistic scenarios."""

    def test_scan_task_realistic_pii_detection(self, mock_env, mock_gliner_model):
        entities = [
            {
                "text": "John Smith",
                "label": "person",
                "start": 0,
                "end": 10,
                "score": 0.96,
            },
            {
                "text": "john@example.com",
                "label": "email address",
                "start": 20,
                "end": 36,
                "score": 0.99,
            },
            {
                "text": "555-1234",
                "label": "phone number",
                "start": 40,
                "end": 48,
                "score": 0.92,
            },
        ]
        mock_gliner_model.predict_entities.return_value = entities

        document = "John Smith, john@example.com, 555-1234"
        result = scan(document)

        assert result["pages"][0]["detections"][0]["pii"] is True
        assert result["pages"][0]["detections"][0]["severity"] == "medium"
        assert len(result["pages"][0]["detections"][0]["entities"]) == 3

    def test_scan_task_multipage_document(self, mock_env, mock_gliner_model):
        mock_gliner_model.predict_entities.side_effect = [
            [
                {
                    "text": "Jane Doe",
                    "label": "person",
                    "start": 0,
                    "end": 8,
                    "score": 0.95,
                }
            ],
            [],
            [
                {
                    "text": "sk-secret123",
                    "label": "API key",
                    "start": 5,
                    "end": 17,
                    "score": 0.99,
                }
            ],
        ]

        input_data = {
            "pages": [
                {"content": "Jane Doe contact info", "page_number": 1},
                {"content": "Normal text", "page_number": 2},
                {"content": "API key: sk-secret123", "page_number": 3},
            ]
        }

        result = scan(input_data)

        assert len(result["pages"]) == 3
        assert result["pages"][0]["detections"][0]["flagged"] is True
        assert result["pages"][1]["detections"][0]["flagged"] is False
        assert result["pages"][2]["detections"][0]["flagged"] is True
        assert result["pages"][2]["detections"][0]["severity"] == "high"

    def test_scan_task_empty_content(self, mock_env, mock_gliner_model):
        mock_gliner_model.predict_entities.return_value = []

        result = scan("")

        assert result["error"] is None
        assert result["pages"][0]["detections"][0]["flagged"] is False
