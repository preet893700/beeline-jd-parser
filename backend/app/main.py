# app/main.py
"""
JD Parser - FastAPI Main Application
Enterprise-grade Job Description Parser with AI extraction

UPDATED: Added progress tracking endpoint
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.mongodb import MongoDBClient
from app.api.v1 import jd_excel, jd_text, health, progress


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown events"""
    # Startup
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting JD Parser API...")
    
    # Initialize MongoDB connection
    await MongoDBClient.connect()
    logger.info("MongoDB connection established")
    
    yield
    
    # Shutdown
    logger.info("Shutting down JD Parser API...")
    await MongoDBClient.close()
    logger.info("MongoDB connection closed")


# Initialize FastAPI application
app = FastAPI(
    title="JD Parser API",
    description="Enterprise Job Description Parser with AI Extraction",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(jd_excel.router, prefix="/api/v1/excel", tags=["Excel JD"])
app.include_router(jd_text.router, prefix="/api/v1/text", tags=["Text JD"])
app.include_router(progress.router, prefix="/api/v1", tags=["Progress"])  # NEW


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "JD Parser API",
        "version": "1.0.0",
        "status": "operational"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )