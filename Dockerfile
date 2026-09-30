# ---------- build the web client ----------
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---------- runtime: FastAPI + numpy inference ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server/ server/
COPY data/build/ data/build/
COPY data/raw/IIMB_BRSR_Report_FY2024-25.pdf data/raw/IIMB_BRSR_Report_FY2024-25.pdf
COPY --from=web /web/dist web/dist
RUN useradd -m pramana && chown -R pramana /app
USER pramana
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health')"
CMD ["sh", "-c", "uvicorn pramana.app:app --app-dir server --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
