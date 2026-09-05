FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first: this layer is cached until pyproject.toml changes.
COPY pyproject.toml ./
COPY vcf_core ./vcf_core
COPY api ./api
COPY config ./config
COPY manage.py ./
RUN pip install --no-cache-dir -e .

COPY data ./data

# Run as a non-root user; give it ownership of data/ so writes and the lock file work.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app/data
USER appuser

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
