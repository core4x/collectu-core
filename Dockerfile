FROM python:3.14.3

# gosu sets up the user environment and then executes (replaces itself with) the Python process.
# Your Python app becomes PID 1. When Docker sends a shutdown signal, it goes directly to Python.
RUN apt-get update && apt-get install -y gosu && rm -rf /var/lib/apt/lists/*

LABEL maintainer="info@collectu.de" \
      org.opencontainers.image.source="https://github.com/core4x/collectu-core" \
      org.opencontainers.image.description="Collectu Core" \
      org.opencontainers.image.version="latest"

# Set environment variables.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_ROOT_USER_ACTION=ignore

# Set default values for the environment variables (if not used with docker-compose).
ENV API_HOST=0.0.0.0
ENV API_PORT=8181
ENV FRONTEND_HOST=0.0.0.0
ENV FRONTEND_PORT=8282

# Default to non-root user (appuser).
ENV RUN_AS_ROOT=0

# Expose the ports of the API and FRONTEND.
EXPOSE 8181
EXPOSE 8282

# Clone project and mark as safe repo.
RUN git clone --depth 1 https://github.com/core4x/collectu-core.git \
 && git config --system --add safe.directory /collectu-core

# Add non-root user.
RUN groupadd -g 1000 appuser \
 && useradd -u 1000 -g 1000 -m -s /bin/bash appuser \
 && chown -R appuser:appuser /collectu-core

USER appuser

# Set working directory.
WORKDIR /collectu-core/src

# Create virtual environment.
ENV VENV_PATH=/collectu-core/venv
RUN python -m venv $VENV_PATH
ENV PATH="$VENV_PATH/bin:$PATH"

# Install requirements.
RUN pip install --upgrade pip --no-cache-dir \
 && pip install --no-cache-dir -r requirements.txt

# Stop using "USER appuser" here so we start as root to fix permissions.
USER root

RUN chmod +x /collectu-core/entrypoint.sh

# Define entrypoint.
ENTRYPOINT ["/collectu-core/entrypoint.sh"]
