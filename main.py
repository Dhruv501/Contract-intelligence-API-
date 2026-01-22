from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager
import asyncio
from typing import List, Optional
import json

from app.routes import router
from app.database import init_db, close_db
from app.metrics import metrics

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()

app = FastAPI(
    title="Contract Intelligence API",
    description="API for ingesting, extracting, analyzing, and querying contract documents",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "contract-intelligence-api"}

@app.get("/metrics")
async def get_metrics():
    """Get basic metrics"""
    return metrics.get_metrics()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

