FROM python:3.12-slim

WORKDIR /app

# Install Docker CLI only (no Docker daemon — we use the host socket)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
       https://download.docker.com/linux/debian bookworm stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py docker_client.py server.py ./

# Non-root user for safety
RUN useradd -r -u 1000 -g root mcpuser \
    && chown -R mcpuser:root /app
USER mcpuser

EXPOSE 8765

CMD ["python", "server.py"]
