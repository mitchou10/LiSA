
BACKEND_DIR := backend

.PHONY: help install lint format run-test test build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install backend dependencies (with dev extras)
	cd $(BACKEND_DIR) && python -m pip install -e ".[dev]"

lint: install ## Run ruff linter
	@echo "Running ruff..."
	cd $(BACKEND_DIR) && ruff check .

format: install ## Auto-format code with ruff
	cd $(BACKEND_DIR) && ruff format . && ruff check --fix .

run-test: install ## Install dependencies and run unit tests
	cd $(BACKEND_DIR) && pytest -q

test: ## Run unit tests (assumes dependencies are installed)
	cd $(BACKEND_DIR) && pytest -q

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(BACKEND_DIR)/.pytest_cache $(BACKEND_DIR)/.ruff_cache $(BACKEND_DIR)/test.db
