FROM python:3.14.3-slim

LABEL maintainer="info@collectu.de" \
      org.opencontainers.image.source="https://github.com/core4x/collectu-core" \
      org.opencontainers.image.description="Collectu Core" \
      org.opencontainers.image.version="latest"

# Set environment variables.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set default values for the environment variables (if not used with docker-compose).
ARG API_HOST=0.0.0.0
ARG API_PORT=8181
ARG FRONTEND_HOST=0.0.0.0
ARG FRONTEND_PORT=8282

ENV API_HOST=${API_HOST}
ENV API_PORT=${API_PORT}
ENV FRONTEND_HOST=${FRONTEND_HOST}
ENV FRONTEND_PORT=${FRONTEND_PORT}

# Expose the ports of the API and FRONTEND.
EXPOSE ${API_PORT}
EXPOSE ${FRONTEND_PORT}

# Clean up apt cache in the same layer to keep image size down.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
 && rm -rf /var/lib/apt/lists/*

# Clone project and mark as safe repo.
RUN git clone --depth 1 https://github.com/core4x/collectu-core.git \
 && git config --system --add safe.directory /collectu-core

# Set working directory.
WORKDIR /collectu-core/src

# Install requirements.
RUN pip install --upgrade pip --no-cache-dir \
 && pip install --no-cache-dir -r requirements.txt

# Define entrypoint.
ENTRYPOINT [ "python", "main.py" ]
