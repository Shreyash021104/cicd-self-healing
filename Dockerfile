# Multi-stage build for the deployable artifact — the sample service that this
# pipeline ships and health-checks. Stage 1 installs dependencies; stage 2 is a
# slim runtime that copies only what's needed, keeping the image small.

# ── Stage 1: build/install dependencies ────────────────────────────────────
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: slim runtime ──────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app
# Copy the installed packages from the builder stage (no build tooling in the final image).
COPY --from=builder /install /usr/local
COPY app ./app

ENV VERSION=docker
EXPOSE 8080

# A readiness/liveness check baked into the image (Kubernetes would use its own probe,
# but this makes `docker run` self-verifying too).
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status==200 else 1)"

# The deployable unit: the sample service the controller rolls out and smoke-tests.
CMD ["uvicorn", "app.service:app", "--host", "0.0.0.0", "--port", "8080"]
