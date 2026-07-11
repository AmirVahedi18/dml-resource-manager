# syntax=docker/dockerfile:1
FROM python:3.11-slim

# tzdata lets the container honor the TZ env var for display timestamps
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .
 
COPY configs ./configs
COPY main.py ./

RUN useradd --create-home --uid 1000 dmlapp \
    && mkdir -p /app/data /app/logs \
    && chown -R dmlapp:dmlapp /app

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

VOLUME ["/app/data", "/app/logs"]

# Container starts as root so the entrypoint can fix ownership on bind-mounted
# ./data and ./logs (host ownership varies per deploy), then drops to dmlapp.
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "main.py"]
