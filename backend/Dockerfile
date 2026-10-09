FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
    build-essential pkg-config libcairo2-dev libpango-1.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-runtime.txt requirements-test.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt -r requirements-test.txt
COPY . .
RUN mkdir -p static/documents/acceptances static/uploads/installations
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
