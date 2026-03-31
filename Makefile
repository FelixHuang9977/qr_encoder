.PHONY: help setup test

help:
	@echo "Available commands:"
	@echo "  make setup   - setup python venv and install dependencies"
	@echo "  make test    - run pytest"
	@echo "  make help    - show this help message"

setup:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt pytest

test:
	./venv/bin/pytest
