FROM python:3.11-slim AS assets
WORKDIR /build
COPY scripts/download_assets.py scripts/assets.json ./scripts/
RUN python scripts/download_assets.py

FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json ./
COPY src ./src
COPY scripts/build.mjs ./scripts/build.mjs
COPY public ./public
COPY --from=assets /build/public ./public
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 MOTIONAI_ENV=production \
    MOTIONAI_AUTH_DB=/var/data/accounts.sqlite MOTIONAI_USER_DATA_DIR=/var/data/users \
    MOTIONAI_DB=/var/data/system.sqlite MOTIONAI_REQUIRE_MODEL=1 PORT=8000
COPY requirements.txt ./
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2.8,<3" \
    && pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY scripts/download_checkpoint.py ./scripts/download_checkpoint.py
RUN python scripts/download_checkpoint.py
COPY --from=frontend /build/dist ./dist
RUN groupadd --gid 10001 motionai && useradd --uid 10001 --gid motionai --no-create-home motionai \
    && mkdir -p /var/data && chown -R motionai:motionai /var/data /app
EXPOSE 8000
CMD ["python", "-m", "backend.container_start"]
