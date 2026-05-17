FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install uv --no-cache-dir

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY src/ ./src/

# Install Allure CLI (requires Java)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless wget unzip \
    && rm -rf /var/lib/apt/lists/*

ARG ALLURE_VERSION=2.27.0
RUN wget -q "https://github.com/allure-framework/allure2/releases/download/${ALLURE_VERSION}/allure-${ALLURE_VERSION}.zip" \
    -O /tmp/allure.zip \
    && unzip -q /tmp/allure.zip -d /opt \
    && ln -s "/opt/allure-${ALLURE_VERSION}/bin/allure" /usr/local/bin/allure \
    && rm /tmp/allure.zip

RUN mkdir -p /app/data /app/allure_reports \
    && useradd -m -u 1000 app \
    && chown -R app:app /app

USER app

EXPOSE 8080

ENTRYPOINT ["uv", "run", "python", "-m", "uvicorn", "app.main:app", \
            "--host", "0.0.0.0", "--port", "8080"]
