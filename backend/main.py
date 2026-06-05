"""
UAE Real Estate Decision Intelligence Platform — FastAPI Backend
Loads all data, builds AI index, and registers all API routes.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.data.loader import data_store
from backend.ai.rag import rag_engine
from backend.api.routes import executive, forecast, market, customer, inventory, ai_studio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.time()
    log.info("═" * 60)
    log.info("  UAE Real Estate Decision Intelligence Platform")
    log.info("  Starting up …")
    log.info("═" * 60)

    # 1. Load all datasets
    data_store.load_all()

    # 2. Build FAISS vector index (try to load existing first)
    if not rag_engine.load_index():
        log.info("Building FAISS index from data lake …")
        rag_engine.build_index(data_store.all())

    log.info("Platform ready in %.1fs  ✓", time.time() - t0)
    log.info("═" * 60)
    yield
    log.info("Shutting down platform …")


app = FastAPI(
    title="UAE Real Estate Decision Intelligence Platform",
    description="AI-powered strategic decision engine for UAE real estate executives.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(executive.router, prefix=API_PREFIX)
app.include_router(forecast.router,  prefix=API_PREFIX)
app.include_router(market.router,    prefix=API_PREFIX)
app.include_router(customer.router,  prefix=API_PREFIX)
app.include_router(inventory.router, prefix=API_PREFIX)
app.include_router(ai_studio.router, prefix=API_PREFIX)


@app.get("/")
def root():
    return {
        "platform": "UAE Real Estate Decision Intelligence Platform",
        "version":  "2.0.0",
        "status":   "operational",
        "docs":     "/docs",
        "endpoints": [
            f"{API_PREFIX}/executive",
            f"{API_PREFIX}/forecast",
            f"{API_PREFIX}/market",
            f"{API_PREFIX}/customer",
            f"{API_PREFIX}/inventory",
            f"{API_PREFIX}/ai",
        ],
    }


@app.get("/health")
def health():
    datasets = {k: len(v) if v is not None else 0 for k, v in data_store.all().items()}
    return {"status": "healthy", "datasets_loaded": len(datasets), "dataset_record_counts": datasets}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    log.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": str(exc)})
