FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# Kopieer dependency-bestanden eerst (Docker layer caching)
COPY pyproject.toml uv.lock ./

# Installeer dependencies (zonder dev-dependencies, geen editable install)
RUN uv sync --frozen --no-dev --no-install-project

# Kopieer de rest van de broncode
COPY . .

# Poort declareren
EXPOSE 8000

# Start de server via uv run (gebruikt de juiste venv automatisch)
CMD [".venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]