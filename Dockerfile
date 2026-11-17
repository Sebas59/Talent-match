# Talent Match V6. Construya antes el frontend (frontend/dist) o use la etapa node.
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY scripts ./scripts
COPY data/*.csv data/*.xlsx ./data/
COPY tests/fixtures ./tests/fixtures
COPY --from=web /web/dist ./frontend/dist
# Usuario sin privilegios (mínimo privilegio, como en V5)
RUN useradd --create-home --uid 10001 talent && chown -R talent /app/data
USER talent
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
