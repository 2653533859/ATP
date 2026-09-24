# Overlay the runtime files changed since the verified bdb84286 image.
# Build context: backend/ (not the repository root).
ARG ATP_BACKEND_BASE_IMAGE=registry.local/atp/backend:bdb84286
FROM ${ATP_BACKEND_BASE_IMAGE}

ARG ATP_HERMES_REVISION=uncommitted
LABEL org.opencontainers.image.revision="${ATP_HERMES_REVISION}"

# The verified base image carries this entrypoint as 0664, so OCI cannot exec it.
RUN chmod 0755 /app/docker-start.sh

COPY app/api/v1/hermes.py /app/app/api/v1/hermes.py
COPY app/api/deps.py /app/app/api/deps.py
COPY app/schemas/hermes.py /app/app/schemas/hermes.py
COPY app/schemas/hermes_orchestration.py /app/app/schemas/hermes_orchestration.py
COPY app/services/hermes.py /app/app/services/hermes.py
COPY app/services/hermes_orchestration.py /app/app/services/hermes_orchestration.py
COPY app/services/audit.py /app/app/services/audit.py
