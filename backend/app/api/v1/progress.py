# app/api/v1/progress.py
"""
Progress Tracking Endpoints
Simple polling-based progress updates
"""

from fastapi import APIRouter, HTTPException
import logging

from app.services.progress.tracker import progress_tracker

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/progress/{request_id}")
async def get_extraction_progress(request_id: str):
    """
    Get extraction progress for a request
    
    Returns:
        {
            "request_id": str,
            "total": int,
            "processed": int,
            "complete": bool
        }
    
    Used by frontend for polling progress updates
    """
    progress = progress_tracker.get_progress(request_id)
    
    if progress is None:
        raise HTTPException(
            status_code=404,
            detail=f"No progress tracking found for request: {request_id}"
        )
    
    return {
        "request_id": request_id,
        "total": progress["total"],
        "processed": progress["processed"],
        "complete": progress["processed"] >= progress["total"]
    }