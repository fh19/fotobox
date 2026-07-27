# Fotobox — developer commands.
# Development happens on the workstation with FOTOBOX_HARDWARE=mock.

VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Local, writable data directory for mock development (the Pi uses /data).
DEV_DATA ?= $(CURDIR)/devdata

.PHONY: dev test lint format fixtures manual install clean

install:
	$(PIP) install -r requirements-dev.txt

dev:
	cd backend && FOTOBOX_HARDWARE=mock FOTOBOX_DATA_DIR=$(DEV_DATA) \
		../$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check backend
	$(VENV)/bin/ruff format --check backend

format:
	$(VENV)/bin/ruff format backend
	$(VENV)/bin/ruff check --fix backend

fixtures:
	$(PY) backend/tools/make_fixtures.py

# Render docs/bedienungsanleitung.md -> docs/bedienungsanleitung.pdf (needs pandoc + chromium).
manual:
	python3 tools/build_manual_pdf.py

clean:
	rm -rf devdata backend/**/__pycache__ .pytest_cache
