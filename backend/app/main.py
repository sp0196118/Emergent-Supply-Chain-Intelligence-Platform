"""
FastAPI application entrypoint.

Registers all routers, enables CORS for the future React dev server
(Phase 7), and exposes a health check. Run locally with:

    uvicorn app.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analytics, optimization, rl, simulation
from app.api.websockets import router as ws_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulation.router)
app.include_router(analytics.router)
app.include_router(optimization.router)
app.include_router(rl.router)
app.include_router(ws_router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}
