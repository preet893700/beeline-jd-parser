# app/services/ai/gemini_service.py
"""
Google Gemini AI Service
"""

import httpx
import logging
import time
from typing import Optional

from app.core.config import settings
from app.core.exceptions import AIExtractionError
from app.services.ai.prompt_templates import (
    JD_EXTRACTION_SYSTEM_PROMPT,
    get_jd_extraction_prompt
)

logger = logging.getLogger(__name__)


class GeminiService:
    """Google Gemini AI service"""
    
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.timeout = settings.GEMINI_TIMEOUT
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
    
    async def extract_jd(self, jd_text: str) -> tuple[str, int]:
        """
        Extract JD using Gemini
        Returns: (response_text, response_time_ms)
        """
        if not self.api_key:
            raise AIExtractionError("Gemini API key not configured")
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/models/{self.model}:generateContent",
                    params={"key": self.api_key},
                    json={
                        "contents": [{
                            "parts": [{
                                "text": self._build_prompt(jd_text)
                            }]
                        }],
                        "generationConfig": {
                            "temperature": 0.1,
                            "topP": 0.9,
                            "topK": 40,
                        }
                    }
                )
                
                response.raise_for_status()
                data = response.json()
                
                response_time = int((time.time() - start_time) * 1000)
                
                # Extract text from Gemini response
                text = self._extract_text(data)
                
                return text, response_time
                
        except httpx.TimeoutException:
            logger.warning(f"Gemini timeout after {self.timeout}s")
            raise AIExtractionError("Gemini request timed out")
        except httpx.HTTPError as e:
            logger.error(f"Gemini HTTP error: {e}")
            raise AIExtractionError(f"Gemini HTTP error: {str(e)}")
        except Exception as e:
            logger.error(f"Gemini extraction error: {e}")
            raise AIExtractionError(f"Gemini error: {str(e)}")
    
    def _build_prompt(self, jd_text: str) -> str:
        """Build complete prompt for Gemini"""
        return f"""{JD_EXTRACTION_SYSTEM_PROMPT}

{get_jd_extraction_prompt(jd_text)}"""
    
    def _extract_text(self, response_data: dict) -> str:
        """Extract text from Gemini API response"""
        try:
            candidates = response_data.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in response")
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            if not parts:
                raise ValueError("No parts in response")
            
            return parts[0].get("text", "")
            
        except Exception as e:
            logger.error(f"Failed to extract text from Gemini response: {e}")
            raise AIExtractionError(f"Invalid Gemini response format: {str(e)}")
    
    async def health_check(self) -> bool:
        """Check if Gemini service is available"""
        if not self.api_key:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.base_url}/models/{self.model}",
                    params={"key": self.api_key}
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False