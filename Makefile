.PHONY: run, run-prod, install, lint

PROJECT_DIR = $(shell pwd)

default: run

install:
	pip install -r requirements.txt

lint:
	@echo "Running lint checks..."
	@ruff check $(PROJECT_DIR) --fix
	@echo "Linting completed."