FROM python:3.11

# Set environment variables.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

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

# Update everything.
RUN pip install --upgrade pip

# Create empty directories which are mapped to the local file system when using docker-compose.
RUN mkdir /configuration
RUN mkdir /logs
RUN mkdir /data

# Copy project.
COPY src /src

# Copy some files.
COPY settings.ini .
COPY LICENSE.md .
COPY README.md .
COPY .gitmodules .
COPY ./configuration/configuration.yml ./configuration

# Set working directory.
WORKDIR /src

# Install requirements.
RUN pip install -r requirements.txt

# Define entrypoint.
ENTRYPOINT [ "python", "main.py" ]
