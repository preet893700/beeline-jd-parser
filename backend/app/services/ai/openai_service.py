# app/services/ai/openai_service.py
"""
OpenAI Service
GPT models integration
"""

import httpx
import logging
import time

from app.core.config import settings
from app.core.exceptions import AIExtractionError
from app.services.ai.prompt_templates import (
    JD_EXTRACTION_SYSTEM_PROMPT,
    get_jd_extraction_prompt
)

logger = logging.getLogger(__name__)


class OpenAIService:
    """OpenAI GPT service"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.timeout = settings.OPENAI_TIMEOUT
        self.base_url = "https://api.openai.com/v1"
    
    async def extract_jd(self, jd_text: str) -> tuple[str, int, dict]:
        """
        Extract JD using OpenAI
        Returns: (response_text, response_time_ms, token_usage)
        """
        if not self.api_key:
            raise AIExtractionError("OpenAI API key not configured")
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": JD_EXTRACTION_SYSTEM_PROMPT
                            },
                            {
                                "role": "user",
                                "content": get_jd_extraction_prompt(jd_text)
                            }
                        ],
                        "temperature": 0.1,
                        "max_tokens": 1000
                    }
                )
                
                response.raise_for_status()
                data = response.json()
                
                response_time = int((time.time() - start_time) * 1000)
                
                # Extract content
                text = data["choices"][0]["message"]["content"]
                
                # Extract token usage
                usage = data.get("usage", {})
                token_usage = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                }
                
                return text, response_time, token_usage
                
        except httpx.TimeoutException:
            logger.warning(f"OpenAI timeout after {self.timeout}s")
            raise AIExtractionError("OpenAI request timed out")
        except httpx.HTTPError as e:
            logger.error(f"OpenAI HTTP error: {e}")
            raise AIExtractionError(f"OpenAI HTTP error: {str(e)}")
        except KeyError as e:
            logger.error(f"OpenAI response missing key: {e}")
            raise AIExtractionError(f"Invalid OpenAI response: {str(e)}")
        except Exception as e:
            logger.error(f"OpenAI extraction error: {e}")
            raise AIExtractionError(f"OpenAI error: {str(e)}")
    
    async def health_check(self) -> bool:
        """Check if OpenAI service is available"""
        if not self.api_key:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False