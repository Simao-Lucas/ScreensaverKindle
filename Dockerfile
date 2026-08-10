FROM python:3.12-slim

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# Calibre via apt (ebook-convert). Mais estável no Docker do que o installer oficial.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        calibre \
    && ebook-convert --version \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/data/uploads /app/data/books/incoming /app/data/books/ready /keys

ENV FLASK_APP=app.main:app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV EBOOK_CONVERT_BIN=ebook-convert

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://127.0.0.1:$${PORT:-8080}/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
