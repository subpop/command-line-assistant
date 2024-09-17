.PHONY: run, run-prod, install, lint

PROJECT_DIR = $(shell pwd)

default: run

install:
	pip install -r requirements-dev.txt

lint:
	@echo "Running lint checks..."
	@ruff check $(PROJECT_DIR) --fix
	@echo "Linting completed."

test:
	@echo "Running tests..."
	@coverage run -m pytest tests
	@coverage report
	@echo "Tests completed."
