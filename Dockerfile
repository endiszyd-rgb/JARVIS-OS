# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS control-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --strict-ssl=true
COPY frontend ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt requirements.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt && \
    useradd -m -u 10001 jarvis && mkdir /app/data && chown jarvis:jarvis /app/data
COPY --chown=jarvis:jarvis jarvis ./jarvis
COPY --chown=jarvis:jarvis third_party ./third_party
COPY --from=control-build --chown=jarvis:jarvis /frontend/dist ./frontend/dist
USER jarvis
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)"
CMD ["python", "-m", "uvicorn", "jarvis.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
