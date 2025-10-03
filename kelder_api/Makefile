.PHONY: test lint format all

test:
	pytest

lint:
	ruff check --fix . --exclude tests/notebooks

format:
	ruff format . --exclude tests/notebooks

all: lint format test
