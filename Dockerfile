FROM python:3.13.14

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

# Default to non-root user (appuser).
ENV RUN_AS_ROOT=0

# One port: the api serves the frontend itself.
EXPOSE 8181

# Clone project at the commit the release workflow passes in (a plain build takes main) and mark as
# safe repo. A full clone rather than --depth 1: it keeps the tags, so the version a container
# reports (git describe) is the release rather than a bare commit hash. The repository is small.
ARG GIT_SHA=main
RUN git clone https://github.com/core4x/collectu-core.git \
 && git -C /collectu-core checkout -B main "$GIT_SHA" \
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
