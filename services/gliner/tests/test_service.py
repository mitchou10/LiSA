"""Tests for GlinerService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.service import CATEGORY_MAP, GlinerService, _severity_for_category


class TestSeverityForCategory:
    """Tests for _severity_for_category() function."""

    def test_high_severity_for_secret(self):
        assert _severity_for_category("SECRET") == "high"

    def test_high_severity_for_police(self):
        assert _severity_for_category("POLICE") == "high"

    def test_medium_severity_for_pii(self):
        assert _severity_for_category("PII") == "medium"

    def test_medium_severity_for_health(self):
        assert _severity_for_category("HEALTH") == "medium"

    def test_medium_severity_for_legal(self):
        assert _severity_for_category("LEGAL") == "medium"

    def test_low_severity_for_unknown(self):
        assert _severity_for_category("UNKNOWN") == "low"


class TestGlinerServiceGetLabels:
    """Tests for GlinerService._get_labels()."""

    def test_get_labels_parses_config(self, mock_env):
        service = GlinerService()
        labels = service._get_labels()
        assert isinstance(labels, list)
        assert "person" in labels
        assert "email address" in labels
        assert "password" in labels

    def test_get_labels_caches_result(self, mock_env):
        service = GlinerService()
        labels1 = service._get_labels()
        labels2 = service._get_labels()
        assert labels1 is labels2  # Same object reference (cached)

    def test_get_labels_strips_whitespace(self, monkeypatch, mock_env):
        monkeypatch.setenv("GLINER_LABELS", "person , email address , password ")
        service = GlinerService()
        labels = service._get_labels()
        assert labels == ["person", "email address", "password"]

    def test_get_labels_handles_empty_strings(self, monkeypatch, mock_env):
        monkeypatch.setenv("GLINER_LABELS", "person,,email address,,")
        service = GlinerService()
        labels = service._get_labels()
        assert labels == ["person", "email address"]


class TestGlinerServiceIterPages:
    """Tests for GlinerService._iter_pages()."""

    def test_iter_pages_with_string_input(self, mock_env):
        service = GlinerService()
        result = service._iter_pages("hello world")
        assert len(result) == 1
        assert result[0]["content"] == "hello world"
        assert result[0]["page_number"] is None

    def test_iter_pages_with_dict_pages(self, mock_env, sample_input_dict_with_pages):
        service = GlinerService()
        result = service._iter_pages(sample_input_dict_with_pages)
        assert len(result) == 2
        assert result[0]["content"] == "Page 1: John Doe lives at 123 Main St"
        assert result[0]["page_number"] == 1
        assert result[1]["content"] == "Page 2: Emergency contact: jane@example.com"
        assert result[1]["page_number"] == 2

    def test_iter_pages_with_dict_content(self, mock_env, sample_input_dict_with_content):
        service = GlinerService()
        result = service._iter_pages(sample_input_dict_with_content)
        assert len(result) == 1
        assert result[0]["content"] == "Contact me at jane@example.com"
        assert result[0]["page_number"] is None

    def test_iter_pages_with_dict_prompt(self, mock_env):
        service = GlinerService()
        result = service._iter_pages({"prompt": "test prompt"})
        assert len(result) == 1
        assert result[0]["content"] == "test prompt"

    def test_iter_pages_with_non_string_input(self, mock_env):
        service = GlinerService()
        result = service._iter_pages(12345)
        assert len(result) == 1
        assert result[0]["content"] == "12345"

    def test_iter_pages_empty_dict(self, mock_env):
        service = GlinerService()
        result = service._iter_pages({})
        assert len(result) == 1
        assert result[0]["content"] == "None"


class TestGlinerServiceScanPage:
    """Tests for GlinerService._scan_page()."""

    def test_scan_page_with_entities(self, mock_env, mock_gliner_model, sample_gliner_entities):
        mock_gliner_model.predict_entities.return_value = sample_gliner_entities

        service = GlinerService()
        result = service._scan_page("Test content")

        assert result["flagged"] is True
        assert result["confidence"] == 0.98  # max of [0.95, 0.98]
        assert result["severity"] == "medium"  # PII category
        assert result["action"] == "redact"
        assert result["pii"] is True
        assert len(result["entities"]) == 2

    def test_scan_page_with_secret_entities(self, mock_env, mock_gliner_model, sample_gliner_entities_with_secrets):
        mock_gliner_model.predict_entities.return_value = sample_gliner_entities_with_secrets

        service = GlinerService()
        result = service._scan_page("Test content with secrets")

        assert result["flagged"] is True
        assert result["severity"] == "high"  # SECRET category
        assert result["action"] == "redact"
        assert result["pii"] is False  # No PII entities

    def test_scan_page_no_entities(self, mock_env, mock_gliner_model):
        mock_gliner_model.predict_entities.return_value = []

        service = GlinerService()
        result = service._scan_page("Clean text with no entities")

        assert result["flagged"] is False
        assert result["confidence"] == 0.0
        assert result["severity"] is None
        assert result["action"] == "allow"
        assert len(result["entities"]) == 0

    def test_scan_page_entity_structure(self, mock_env, mock_gliner_model):
        entities = [
            {
                "text": "john@example.com",
                "label": "email address",
                "start": 10,
                "end": 26,
                "score": 0.99,
            }
        ]
        mock_gliner_model.predict_entities.return_value = entities

        service = GlinerService()
        result = service._scan_page("Contact: john@example.com")

        assert len(result["entities"]) == 1
        entity = result["entities"][0]
        assert entity["id"] == "e0"
        assert entity["type"] == "PII"
        assert entity["label"] == "email address"
        assert entity["text"] == "john@example.com"
        assert entity["start_char"] == 10
        assert entity["end_char"] == 26
        assert entity["confidence"] == 0.99
        assert entity["flagged"] is True

    def test_scan_page_unknown_label_mapping(self, mock_env, mock_gliner_model):
        entities = [
            {
                "text": "unknown_entity",
                "label": "unknown_category",
                "start": 0,
                "end": 14,
                "score": 0.8,
            }
        ]
        mock_gliner_model.predict_entities.return_value = entities

        service = GlinerService()
        result = service._scan_page("unknown_entity")

        entity = result["entities"][0]
        assert entity["type"] == "OTHER"  # Default category


class TestGlinerServiceProcess:
    """Tests for GlinerService.process()."""

    def test_process_single_page(self, mock_env, mock_gliner_model, sample_gliner_entities):
        mock_gliner_model.predict_entities.return_value = sample_gliner_entities

        service = GlinerService()
        result = service.process("Test content", task_id="test-task-123")

        assert result["id"] == "test-task-123"
        assert len(result["pages"]) == 1
        assert result["error"] is None
        assert result["pages"][0]["page_number"] is None
        assert len(result["pages"][0]["detections"]) == 1

    def test_process_multiple_pages(self, mock_env, mock_gliner_model):
        mock_gliner_model.predict_entities.side_effect = [
            [
                {
                    "text": "John",
                    "label": "person",
                    "start": 0,
                    "end": 4,
                    "score": 0.9,
                }
            ],
            [],  # Second page has no entities
        ]

        input_data = {
            "pages": [
                {"content": "John works here", "page_number": 1},
                {"content": "Clean page", "page_number": 2},
            ]
        }

        service = GlinerService()
        result = service.process(input_data, task_id="multi-page-task")

        assert len(result["pages"]) == 2
        assert result["pages"][0]["page_number"] == 1
        assert result["pages"][1]["page_number"] == 2
        assert len(result["pages"][0]["detections"][0]["entities"]) == 1
        assert len(result["pages"][1]["detections"][0]["entities"]) == 0

    def test_process_generates_id_when_none(self, mock_env, mock_gliner_model):
        mock_gliner_model.predict_entities.return_value = []

        service = GlinerService()
        result = service.process("content")

        assert result["id"].startswith("gliner-")
        assert result["error"] is None

    def test_process_handles_exception(self, mock_env, mock_gliner_model):
        mock_gliner_model.predict_entities.side_effect = RuntimeError("Model error")

        service = GlinerService()

        with pytest.raises(RuntimeError, match="Model error"):
            service.process("content", task_id="error-task")

    def test_process_normalizes_string_content(self, mock_env, mock_gliner_model):
        mock_gliner_model.predict_entities.return_value = []

        service = GlinerService()
        result = service.process("string input")

        assert len(result["pages"]) == 1
        assert result["pages"][0]["detections"][0]["classification"] == "gliner_ner"

    def test_process_includes_details(self, mock_env, mock_gliner_model, sample_gliner_entities):
        mock_gliner_model.predict_entities.return_value = sample_gliner_entities

        service = GlinerService()
        result = service.process("content")

        details = result["pages"][0]["detections"][0]["details"]
        assert details["model"] == "test-model"
        assert "person" in details["labels"]
        assert details["num_entities"] == 2


class TestGlinerServiceIntegration:
    """Integration tests for the full service flow."""

    def test_full_flow_with_multiple_entity_types(self, mock_env, mock_gliner_model):
        """Test complete flow with multiple entity types across pages."""
        page1_entities = [
            {"text": "John Doe", "label": "person", "start": 0, "end": 8, "score": 0.95},
            {"text": "sk-123", "label": "API key", "start": 20, "end": 26, "score": 0.99},
        ]
        page2_entities = [
            {"text": "evidence file", "label": "evidence", "start": 0, "end": 13, "score": 0.88},
        ]

        mock_gliner_model.predict_entities.side_effect = [page1_entities, page2_entities]

        input_data = {
            "pages": [
                {"content": "Author: John Doe, API: sk-123", "page_number": 1},
                {"content": "Police: evidence file located", "page_number": 2},
            ]
        }

        service = GlinerService()
        result = service.process(input_data)

        # Page 1 checks
        page1_detections = result["pages"][0]["detections"][0]
        assert page1_detections["flagged"] is True
        assert page1_detections["severity"] == "high"  # HIGH because of API key
        assert any(e["type"] == "PII" for e in page1_detections["entities"])
        assert any(e["type"] == "SECRET" for e in page1_detections["entities"])

        # Page 2 checks
        page2_detections = result["pages"][1]["detections"][0]
        assert page2_detections["flagged"] is True
        assert page2_detections["severity"] == "high"  # HIGH because of POLICE
        assert any(e["type"] == "POLICE" for e in page2_detections["entities"])

    def test_model_lazy_loading(self, mock_env, mock_gliner_model):
        """Verify model is loaded once and reused."""
        mock_gliner_model.predict_entities.return_value = []

        service = GlinerService()

        # First process call
        service.process("content 1")
        first_call_count = mock_gliner_model.predict_entities.call_count

        # Second process call
        service.process("content 2")
        second_call_count = mock_gliner_model.predict_entities.call_count

        # Model should be the same instance
        assert service._model is mock_gliner_model
        assert second_call_count == 2  # One call per process()
