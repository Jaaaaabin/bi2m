# Self-hosted bi2m: the built viewer, its API (viewer/
# server/) and the Python recognition pipeline in one container. See
# README.md "Host with Docker". Development does not use this file.

# 1. Viewer build. Dev dependencies are pruned afterwards; three and web-ifc
#    stay, because scripts/tileIfc.mjs tiles uploads at runtime.
FROM node:24-bookworm-slim AS web
WORKDIR /app/viewer
COPY viewer/package.json viewer/package-lock.json ./
RUN npm ci
COPY viewer/ ./
RUN npm run build && npm prune --omit=dev

# 2. Python environment from uv.lock, without the dev group (playwright).
FROM python:3.12-slim-bookworm AS py
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# 3. Runtime: Node serves the viewer and /api, and starts recognition with
#    the venv's interpreter (BI2M_PYTHON) instead of `uv run`.
FROM python:3.12-slim-bookworm
COPY --from=web /usr/local/bin/node /usr/local/bin/node
ENV PATH=/app/.venv/bin:$PATH \
    BI2M_PYTHON=/app/.venv/bin/python \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000
WORKDIR /app
COPY --from=py /app/.venv /app/.venv
COPY pyproject.toml paths.yaml ./
COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/
COPY --from=web /app/viewer /app/viewer
# Everything the server writes is world-writable, so the container runs as
# whatever uid docker-compose.yml passes (BI2M_UID) and can still write into
# a bind-mounted data/ owned by that user on the host.
RUN mkdir -p data/uploads \
        viewer/public/res/intents viewer/public/tiles \
 && chmod -R a+rwX data viewer/public/res viewer/public/tiles
USER 1000:1000
EXPOSE 3000
CMD ["node", "viewer/server/serve.mjs"]
