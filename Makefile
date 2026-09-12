# Makefile for Lumina Career ROI
.PHONY: help up down seed test lint ingest api frontend

help:
	@echo "Lumina Career ROI — Development Commands"
	@echo ""
	@echo "  make up        Start all services (Docker Compose)"
	@echo "  make down      Stop all services"
	@echo "  make seed      Generate seed data (Silver + Gold marts)"
	@echo "  make test      Run backend test suite"
	@echo "  make lint      Run ruff lint on backend"
	@echo "  make ingest    Run the multi-source ingestion pipeline"
	@echo "  make api       Start the FastAPI backend locally"
	@echo "  make frontend  Start the Next.js frontend locally"

up:
	docker compose up -d

down:
	docker compose down

seed:
	PYTHONPATH=. uv run python scripts/seed_data.py

test:
	PYTHONPATH=. uv run pytest tests/ -v

lint:
	uv run ruff check src/ scripts/ tests/ --fix

ingest:
	PYTHONPATH=. uv run python scripts/orchestrator.py

api:
	PYTHONPATH=. uv run uvicorn main:app --reload --port 8000

frontend:
	cd frontend && npm run dev