"""
Mock ia-commander pour tests Hermes en local Mac (path A).

Mime l'API du daemon Rust ia-commander (192.168.1.20:8090) en utilisant FastAPI
+ httpx, en forwarding les chat completions vers claude-code-server distant.

Usage :
    uvicorn server:app --port 8090 --host 0.0.0.0
    (puis dans Hermes config.yaml, pointer base_url vers http://localhost:8090/v1)

Endpoints reproduits :
    GET  /status              -> {"active": ...}
    GET  /variants            -> liste statique des variants
    GET  /health              -> "ok"
    POST /switch/<variant>    -> simule un switch (instantané, pas de vrai llama-server)
    POST /v1/chat/completions -> forward vers CLAUDE_CODE_SERVER_URL
    GET  /v1/models           -> stub OpenAI list

Variables d'environnement requises :
    CLAUDE_CODE_SERVER_URL    (ex: https://openai-claude.fripp.fr)
    CLAUDE_CODE_SERVER_KEY    (API key)

Variables optionnelles :
    MOCK_DEFAULT_VARIANT       (default: qwen36-mtp)
    MOCK_GPU_BUSY              (set "1" pour simuler GPU contention)
"""

import os
import time
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse


CLAUDE_URL = os.environ.get("CLAUDE_CODE_SERVER_URL", "https://openai-claude.fripp.fr")
CLAUDE_KEY = os.environ.get("CLAUDE_CODE_SERVER_KEY", "")
DEFAULT_VARIANT = os.environ.get("MOCK_DEFAULT_VARIANT", "qwen36-mtp")
SIMULATE_BUSY = os.environ.get("MOCK_GPU_BUSY", "0") == "1"

VARIANTS = [
    {"id": "qwen36", "display_name": "Qwen3.6 35B A3B (HauhauCS Aggressive uncensored)"},
    {"id": "qwen36-27b-davidau", "display_name": "Qwen3.6 27B Q5_K_M DavidAU (Heretic NEO-CODE)"},
    {"id": "qwen36-27b-mtp", "display_name": "Qwen3.6 27B Q5_K_M MTP"},
    {"id": "qwen36-mtp", "display_name": "Qwen3.6 35B A3B MTP llmfan46 (mock)"},
    {"id": "gemma4", "display_name": "Gemma 4 31B"},
    {"id": "holo3", "display_name": "Holo3 35B A3B"},
]

# In-memory state
state = {
    "active_variant": None,  # set via /switch
    "started_at": None,
    "switch_count": 0,
}

app = FastAPI(title="ia-commander mock", version="0.1.0")
http = httpx.AsyncClient(timeout=600.0)


@app.get("/health")
async def health():
    return "ok"


@app.get("/status")
async def status():
    if state["active_variant"] is None:
        return {"active": False}
    return {
        "active": {
            "service_id": "llamacpp",
            "variant_id": state["active_variant"],
            "pid": 99999,
        },
        "started_at": state["started_at"],
    }


@app.get("/variants")
async def variants():
    return {"default": DEFAULT_VARIANT, "service": "llamacpp", "variants": VARIANTS}


@app.post("/switch/{variant_id}")
async def switch(variant_id: str):
    if SIMULATE_BUSY:
        # Simule un GPU busy (test du fallback côté skill)
        raise HTTPException(503, detail="GPU busy (mock)")

    if variant_id not in [v["id"] for v in VARIANTS]:
        raise HTTPException(404, detail=f"variant {variant_id} not found")

    # Simule le ready time (10s pour qwen36-mtp en prod, ici instantané)
    state["active_variant"] = variant_id
    state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["switch_count"] += 1

    return {
        "status": "ready",
        "variant_id": variant_id,
        "switch_count": state["switch_count"],
    }


@app.get("/v1/models")
async def models():
    return {
        "object": "list",
        "data": [{"id": v["id"], "object": "model", "created": 0, "owned_by": "ia-commander-mock"} for v in VARIANTS],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Forward to claude-code-server, replacing model name with Claude target."""
    if not CLAUDE_KEY:
        raise HTTPException(500, detail="CLAUDE_CODE_SERVER_KEY not set in env")

    body = await request.json()
    is_stream = body.get("stream", False)

    # Override model: any incoming model -> claude-opus-4 (le serveur a son propre routing)
    body["model"] = body.get("model", "claude-opus-4")
    if body["model"] in [v["id"] for v in VARIANTS]:
        body["model"] = "claude-opus-4"

    headers = {
        "Authorization": f"Bearer {CLAUDE_KEY}",
        "Content-Type": "application/json",
    }
    target = f"{CLAUDE_URL}/v1/chat/completions"

    if is_stream:
        async def stream_gen():
            async with http.stream("POST", target, json=body, headers=headers) as r:
                async for chunk in r.aiter_bytes():
                    yield chunk
        return StreamingResponse(stream_gen(), media_type="text/event-stream")

    r = await http.post(target, json=body, headers=headers)
    return JSONResponse(content=r.json(), status_code=r.status_code)


@app.post("/v1/completions")
async def completions(request: Request):
    return await chat_completions(request)


@app.post("/v1/embeddings")
async def embeddings(request: Request):
    body = await request.json()
    headers = {
        "Authorization": f"Bearer {CLAUDE_KEY}",
        "Content-Type": "application/json",
    }
    r = await http.post(f"{CLAUDE_URL}/v1/embeddings", json=body, headers=headers)
    return JSONResponse(content=r.json(), status_code=r.status_code)
