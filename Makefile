
BACKEND_DIR := backend

.PHONY: help install lint format run-test test build clean erd

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install backend dependencies (with dev extras)
	cd $(BACKEND_DIR) && python -m pip install -e ".[dev]"

lint: install ## Run ruff (check + format check) on backend, worker and services
	@echo "Running ruff..."
	cd $(BACKEND_DIR) && ruff check . && ruff format --check .
	ruff check worker services && ruff format --check worker services

format: install ## Auto-format code with ruff
	cd $(BACKEND_DIR) && ruff format . && ruff check --fix .
	ruff format worker services && ruff check --fix worker services

run-test: install ## Install dependencies and run unit tests
	cd $(BACKEND_DIR) && pytest -q

test: ## Run unit tests (assumes dependencies are installed)
	cd $(BACKEND_DIR) && pytest -q

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(BACKEND_DIR)/.pytest_cache $(BACKEND_DIR)/.ruff_cache $(BACKEND_DIR)/test.db

erd: ## Regenerate the data model diagram (docs/data-model.png) from the models
	cd $(BACKEND_DIR) && uv run --with-editable . --with eralchemy2 python scripts/generate_erd.py ../docs/data-model.png
