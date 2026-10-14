# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS dependencies
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
    build-essential pkg-config libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-runtime.txt requirements-runtime.lock.txt ./
RUN python -m venv /opt/venv
RUN --mount=type=cache,target=/root/.cache/pip /opt/venv/bin/pip install -r requirements-runtime.txt -c requirements-runtime.lock.txt

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"
WORKDIR /app
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends libcairo2 libpango-1.0-0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 noc && useradd --uid 10001 --gid noc --no-create-home noc \
    && mkdir -p static/documents/acceptances static/uploads/installations private_documents \
    && chown -R noc:noc /app
COPY --from=dependencies /opt/venv /opt/venv
COPY --chown=noc:noc app ./app
COPY --chown=noc:noc alembic ./alembic
COPY --chown=noc:noc scripts ./scripts
COPY --chown=noc:noc alembic.ini ./
USER noc
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Preview volumes predate the non-root runtime. Keep their ownership intact.
FROM runtime AS development
USER root
COPY requirements-test.txt ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-test.txt
COPY tests ./tests
COPY pytest.ini ./

FROM runtime AS production
