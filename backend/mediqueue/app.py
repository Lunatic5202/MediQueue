"""FastAPI application factory: lifespan, WebSocket, static frontend, root."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import api
from .config import get_settings
from .db import dispose_engine, get_engine, init_db
from .modules.inference import InferenceError, get_inference_engine
from .realtime import hub
from .security import decode_token, ensure_seed_users

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("mediqueue")


def _try_load_model() -> None:
    engine = get_inference_engine()
    try:
        engine.load()
        logger.info("model loaded: %s", engine.info().get("model_version_id"))
    except InferenceError as exc:
        # Fail-safe: the API still runs; observations will mark prior scores
        # stale rather than inventing scores.
        logger.warning("model not loaded (%s); inference will fail safe", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings().validate_for_startup()
    init_db(get_engine())
    if get_settings().seed_users:
        ensure_seed_users()
    else:
        logger.info("demo seed users disabled (MEDIQUEUE_SEED_USERS=false)")
    _try_load_model()
    yield
    dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="MediQueue",
        version=__version__,
        description=(
            "AI-powered early-warning and dynamic-triage decision support "
            "(prototype). All final triage decisions remain with clinicians."
        ),
        lifespan=lifespan,
    )
    origins = settings.cors_origin_list() or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        # Browsers reject credentials with a wildcard origin; only enable with explicit origins.
        allow_credentials="*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api)

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket, token: str | None = Query(default=None)) -> None:
        if token is None:
            # Also accept token via protocol header for browser clients.
            token = ws.headers.get("x-mq-token")
        payload = decode_token(token) if token else None
        if payload is None:
            await ws.close(code=4401)
            return
        await hub.connect(ws)
        try:
            while True:
                # Keepalive: client may send pings; ignore payloads.
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await hub.disconnect(ws)

    @app.get("/api/meta/frontend", include_in_schema=False)
    def frontend_meta() -> dict:
        dist = Path("frontend/dist")
        return {"dist_exists": (dist / "index.html").exists()}

    dist_dir = Path("frontend/dist")
    if dist_dir.exists():
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str) -> object:  # noqa: ARG001
            from fastapi.responses import FileResponse

            candidate = dist_dir / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(
                dist_dir / "index.html",
                headers={"Cache-Control": "no-cache, must-revalidate"},
            )

    return app


app = create_app()
