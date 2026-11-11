# Etapa 1: gera a tela React.
FROM node:22.23.4-slim AS tela
WORKDIR /tela
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Etapa 2: backend Python servindo a API e a tela.
FROM python:3.13.5-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/app ./app
COPY --from=tela /tela/dist ./static
RUN useradd --create-home atende && mkdir -p dados && chown atende dados
USER atende
ENV ATENDE_PROVEDOR=regras
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
