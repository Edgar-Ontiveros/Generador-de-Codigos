# Dockerfile multi-stage: build de React -> FastAPI sirviendo API + estáticos.
# UN SOLO contenedor: SQLite es una librería sobre un archivo (no va en otro
# contenedor) y el catálogo vive en memoria (no replicar el backend).

# ---------- Etapa 1: build del frontend ----------
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ---------- Etapa 2: backend + estáticos ----------
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/build_db.py backend/core.py backend/main.py ./
COPY data/ ./data/
COPY --from=frontend /build/dist ./static

# catalogo.db vive bajo data/ para que las altas sobrevivan a redeploys:
# montar el volumen (EBS en EC2) con -v ./data:/app/data
ENV CATALOGO_DB=/app/data/catalogo.db

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000
# El entrypoint crea la BD solo si no existe en el volumen; si existe la
# preserva (las altas nunca se pierden) y solo arranca uvicorn.
ENTRYPOINT ["/docker-entrypoint.sh"]
