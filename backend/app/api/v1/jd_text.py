# app/api/v1/jd_text.py
"""
Text JD Extraction Endpoints
"""

from fastapi import APIRouter, HTTPException
import logging

from app.models.jd_result import TextJDRequest, TextJDResponse
from app.services.jd.extractor import JDExtractor
from app.core.exceptions import AIExtractionError

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/extract", response_model=TextJDResponse)
async def extract_from_text(request: TextJDRequest):
    """
    Extract JD data from text
    Processes a single job description
    """
    try:
        if not request.jd_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Job description text cannot be empty"
            )
        
        # Extract JD
        extractor = JDExtractor()
        result = await extractor.extract_from_text(request.jd_text)
        
        return result
        
    except AIExtractionError as e:
        logger.error(f"AI extraction error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"AI extraction failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to extract JD data"
        )