# app/services/ai/ollama_service.py
"""
Ollama AI Service
Local LLM service integration
"""

import httpx
import logging
from typing import Optional
import time

from app.core.config import settings
from app.core.exceptions import AIExtractionError
from app.services.ai.prompt_templates import (
    JD_EXTRACTION_SYSTEM_PROMPT,
    get_jd_extraction_prompt
)

logger = logging.getLogger(__name__)


class OllamaService:
    """Ollama local LLM service"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT
    
    async def extract_jd(self, jd_text: str) -> tuple[str, int]:
        """
        Extract JD using Ollama
        Returns: (response_text, response_time_ms)
        """
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": self._build_prompt(jd_text),
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "top_p": 0.9,
                        }
                    }
                )
                
                response.raise_for_status()
                data = response.json()
                
                response_time = int((time.time() - start_time) * 1000)
                
                return data.get("response", ""), response_time
                
        except httpx.TimeoutException:
            logger.warning(f"Ollama timeout after {self.timeout}s")
            raise AIExtractionError("Ollama request timed out")
        except httpx.HTTPError as e:
            logger.error(f"Ollama HTTP error: {e}")
            raise AIExtractionError(f"Ollama HTTP error: {str(e)}")
        except Exception as e:
            logger.error(f"Ollama extraction error: {e}")
            raise AIExtractionError(f"Ollama error: {str(e)}")
    
    def _build_prompt(self, jd_text: str) -> str:
        """Build complete prompt for Ollama"""
        return f"""{JD_EXTRACTION_SYSTEM_PROMPT}

{get_jd_extraction_prompt(jd_text)}"""
    
    async def health_check(self) -> bool:
        """Check if Ollama service is available"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False