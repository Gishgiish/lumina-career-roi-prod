# Dockerfile (For the ETL Batch Pipeline)
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./
COPY src ./src/

# Install dependencies (frozen for reproducibility)
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the application code
COPY . .

# CRITICAL: Set PYTHONPATH so the 'src' module is discoverable
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# By default, this container will run the orchestrator. 
# (In docker-compose, we can override this command if we just want it to sit idle until scheduled)
CMD ["uv", "run", "python", "scripts/orchestrator.py"]