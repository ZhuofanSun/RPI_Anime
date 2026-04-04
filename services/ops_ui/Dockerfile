FROM python:3.13-slim

WORKDIR /app
ENV PYTHONPATH=/app/services/ops_ui/src:/app/services/postprocessor/src

COPY services/ops_ui/pyproject.toml /app/services/ops_ui/pyproject.toml
COPY services/ops_ui/src /app/services/ops_ui/src
COPY services/postprocessor/pyproject.toml /app/services/postprocessor/pyproject.toml
COPY services/postprocessor/src /app/services/postprocessor/src

RUN pip install --no-cache-dir /app/services/postprocessor /app/services/ops_ui

CMD ["python", "-m", "anime_ops_ui.main"]
