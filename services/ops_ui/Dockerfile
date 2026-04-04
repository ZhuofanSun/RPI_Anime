FROM python:3.13-slim

WORKDIR /app
ENV PYTHONPATH=/app/src

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN pip install --no-cache-dir .

CMD ["python", "-m", "anime_ops_ui.main"]
