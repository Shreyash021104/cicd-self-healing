"""The sample application being deployed — a tiny HTTP service, one instance per
"pod". It exposes the two endpoints a real deploy pipeline probes:

  GET /health  — the readiness/liveness probe (is the pod up and serving?)
  GET /work    — the critical business path the post-deploy SMOKE TEST hits

Two failure modes can be injected via env, to model the two ways a deploy goes
bad:
  BROKEN_HEALTH=1 — /health never returns 200 (readiness gate never opens)
  BROKEN_WORK=1   — /health is fine but /work 500s (looks healthy, but the
                    critical path is broken — exactly what a smoke test catches)
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Response

VERSION = os.getenv("VERSION", "v1")
BROKEN_HEALTH = os.getenv("BROKEN_HEALTH") == "1"
BROKEN_WORK = os.getenv("BROKEN_WORK") == "1"

app = FastAPI()


@app.get("/health")
async def health():
    if BROKEN_HEALTH:
        return Response('{"ok":false}', status_code=503, media_type="application/json")
    return {"ok": True, "version": VERSION}


@app.get("/work")
async def work():
    if BROKEN_WORK:
        return Response('{"error":"critical path broken"}', status_code=500,
                        media_type="application/json")
    return {"result": "ok", "version": VERSION}


@app.get("/version")
async def version():
    return {"version": VERSION}
