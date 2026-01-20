# app/api/v1/health.py
"""
Health Check Endpoints
"""

from fastapi import APIRouter
from datetime import datetime

from app.services.ai.orchestrator import AIOrchestrator

router = APIRouter()


@router.get("/health")
async def health_check():
    """System health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "JD Parser API",
        "version": "1.0.0"
    }


@router.get("/health/ai")
async def ai_health_check():
    """AI services health check"""
    orchestrator = AIOrchestrator()
    services_status = await orchestrator.health_check()
    
    all_healthy = any(services_status.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": services_status,
        "timestamp": datetime.utcnow().isoformat()
    }