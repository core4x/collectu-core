FROM python:3.14.3

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

WORKDIR /collectu-core/src

# Install requirements.
RUN pip install --upgrade pip --no-cache-dir \
 && pip install --no-cache-dir -r requirements.txt

# Define entrypoint.
ENTRYPOINT [ "python", "main.py" ]
