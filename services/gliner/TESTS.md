# GLiNER Service Tests

Comprehensive unit and integration tests for the GLiNER Named Entity Recognition service.

## Test Structure

```
tests/
├── __init__.py              # Test package marker
├── conftest.py              # Pytest configuration and shared fixtures
├── test_service.py          # Tests for GlinerService class
└── test_tasks.py            # Tests for Celery tasks
```

## Test Coverage

### test_service.py

#### TestSeverityForCategory
- Tests the `_severity_for_category()` function
- Verifies correct severity levels (high/medium/low) for each entity category
- Tests: SECRET, POLICE (high), PII, HEALTH, LEGAL (medium), UNKNOWN (low)

#### TestGlinerServiceGetLabels
- Tests the `_get_labels()` method
- Verifies config parsing from environment variables
- Tests: label caching, whitespace stripping, empty string handling

#### TestGlinerServiceIterPages
- Tests the `_iter_pages()` method for input normalization
- Handles: string input, dict with pages, dict with content, dict with prompt
- Tests: page number preservation, default values

#### TestGlinerServiceScanPage
- Tests the `_scan_page()` method
- Verifies: entity detection, severity calculation, action assignment
- Tests: with entities, without entities, unknown labels, entity structure

#### TestGlinerServiceProcess
- Tests the `process()` method
- Handles: single page, multiple pages, exception handling
- Tests: ID generation, result structure, detail inclusion

#### TestGlinerServiceIntegration
- Full workflow tests with realistic data
- Tests: multiple entity types, severity precedence, lazy model loading

### test_tasks.py

#### TestGetService
- Tests the `get_service()` singleton
- Verifies: caching behavior, cache hits/misses

#### TestScanTask
- Tests the `scan()` Celery task
- Tests: service integration, input handling, exception propagation

#### TestScanTaskIntegration
- Realistic scenario tests
- Tests: PII detection, multipage documents, empty content

## Running Tests

### Prerequisites

Install test dependencies:

```bash
pip install -e ".[dev]"
```

This installs:
- `pytest>=8.0` - Test framework
- `pytest-mock>=3.12` - Mocking support

### Run All Tests

```bash
pytest
```

### Run Specific Test Class

```bash
pytest tests/test_service.py::TestGlinerServiceProcess
```

### Run Specific Test

```bash
pytest tests/test_service.py::TestGlinerServiceProcess::test_process_single_page
```

### Run with Coverage

```bash
pip install pytest-cov
pytest --cov=app --cov-report=html
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Short Traceback

```bash
pytest --tb=short
```

## Fixtures

Common fixtures defined in `conftest.py`:

- `mock_env` - Sets default environment variables (auto-used)
- `mock_gliner_model` - Mocks the GLiNER model to avoid downloads
- `sample_input_single_string` - Sample string input
- `sample_input_dict_with_content` - Sample dict with content field
- `sample_input_dict_with_pages` - Sample dict with pages array
- `sample_gliner_entities` - Sample GLiNER model output with person and email
- `sample_gliner_entities_with_secrets` - Sample output with API key and password

## Test Strategy

### Mocking

The tests use `pytest-mock` to mock the GLiNER model, avoiding:
- Model downloads (slow, requires internet)
- GPU requirements
- Environment dependencies

### Isolation

Each test is independent and can run in any order:
- Environment variables are mocked
- Model is mocked
- Service instances don't persist between tests (no caching issues)

### Coverage

The tests cover:
- **Input normalization**: Various input formats (string, dict, list)
- **Entity detection**: With/without entities, confidence scoring
- **Category mapping**: Label-to-category conversion, unknown labels
- **Severity calculation**: Per-category defaults
- **Action assignment**: Redact vs allow
- **Error handling**: Exception propagation and logging
- **Integration**: Full processing pipeline with multiple entities and pages

## CI/CD Integration

Add to your CI pipeline:

```bash
pytest --cov=app --cov-report=xml --junit-xml=test-results.xml
```

This produces:
- Coverage report in `coverage.xml`
- Test results in `test-results.xml` (for CI dashboards)
