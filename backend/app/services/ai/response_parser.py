# app/services/ai/response_parser.py
"""
AI Response Parser
Defensive parsing of AI outputs to structured data
"""

import json
import re
import logging
from typing import Dict, Any, Optional

from app.models.jd_result import JDExtractionResult, ExtractionStatus
from app.core.exceptions import AIExtractionError

logger = logging.getLogger(__name__)


class AIResponseParser:
    """Parse and validate AI responses"""
    
    @staticmethod
    def parse_extraction_response(
        raw_response: str,
        model_name: str
    ) -> JDExtractionResult:
        """
        Parse AI response to JDExtractionResult
        Handles markdown, extra text, and malformed JSON
        """
        try:
            # Clean response
            cleaned = AIResponseParser._clean_response(raw_response)
            
            # Parse JSON
            data = json.loads(cleaned)
            
            # Validate required structure
            if not isinstance(data, dict):
                raise AIExtractionError("Response is not a JSON object")
            
            # Build result
            result = JDExtractionResult(
                bill_rate=data.get("bill_rate"),
                duration=data.get("duration"),
                experience_required=data.get("experience_required"),
                gbams_rgs_id=data.get("gbams_rgs_id"),
                ai_location=data.get("ai_location"),
                skills=data.get("skills") if isinstance(data.get("skills"), list) else None,
                role_description=data.get("role_description"),
                msp_owner=data.get("msp_owner"),
                ai_model_used=model_name,
                ai_extraction_status=ExtractionStatus.SUCCESS
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}, Response: {raw_response[:200]}")
            raise AIExtractionError(f"Failed to parse JSON: {str(e)}")
        except Exception as e:
            logger.error(f"Extraction parsing error: {e}")
            raise AIExtractionError(f"Failed to parse extraction: {str(e)}")
    
    @staticmethod
    def _clean_response(text: str) -> str:
        """
        Clean AI response text
        - Remove markdown code blocks
        - Extract JSON from mixed content
        - Strip whitespace
        """
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Try to extract JSON object
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        
        return text.strip()
    
    @staticmethod
    def create_fallback_result(error_msg: str) -> JDExtractionResult:
        """Create a fallback result when extraction fails completely"""
        return JDExtractionResult(
            ai_extraction_status=ExtractionStatus.FAILED,
            role_description=f"Extraction failed: {error_msg}"
        )