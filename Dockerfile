# The Node and Python stages use the same Debian release so native modules and
# the pinned Playwright browser run in the final image.
FROM node:22.21.1-bookworm-slim AS node
FROM python:3.12.12-slim-bookworm AS build
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.6
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY package.json package-lock.json tsconfig.base.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/music/package.json packages/music/package.json
RUN npm ci
COPY apps/web/ apps/web/
COPY packages/music/ packages/music/
COPY server/ server/
RUN npm run build && uv sync --frozen --no-dev

FROM python:3.12.12-slim-bookworm AS runtime
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && groupadd --gid 10001 songbook && useradd --uid 10001 --gid 10001 --create-home songbook
WORKDIR /app
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/songbook-browsers \
    SONGBOOK_LIBRARY_ROOT=/data \
    SONGBOOK_WORKER_REQUIRED=true \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1
COPY --from=build /app /app
RUN apt-get update && apt-get install -y --no-install-recommends socat libatomic1 \
 && /app/.venv/bin/python -m playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /data && chown -R 10001:10001 /app /data /opt/songbook-browsers
USER 10001:10001
EXPOSE 8080
CMD ["sh", "-c", "songbook serve --host 127.0.0.1 --port 8000 & api=$!; trap 'kill $api 2>/dev/null' EXIT INT TERM; socat TCP-LISTEN:8080,reuseaddr,fork TCP:127.0.0.1:8000"]
