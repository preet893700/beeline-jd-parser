# app/services/ai/orchestrator.py
"""
AI Service Orchestrator
Manages fallback chain: Ollama → Gemini → OpenAI
"""

import logging
from datetime import datetime
from typing import Optional

from app.core.config import settings
from app.core.exceptions import AIExtractionError, AIServiceUnavailableError
from app.models.jd_result import JDExtractionResult, ExtractionStatus, AIAuditLog
from app.services.ai.ollama_service import OllamaService
from app.services.ai.gemini_service import GeminiService
from app.services.ai.openai_service import OpenAIService
from app.services.ai.response_parser import AIResponseParser
from app.repositories.jd_repository import JDRepository

logger = logging.getLogger(__name__)


class AIOrchestrator:
    """
    AI service orchestrator with intelligent fallback
    Tries services in order: Ollama → Gemini → OpenAI
    """
    
    def __init__(self):
        self.ollama = OllamaService()
        self.gemini = GeminiService()
        self.openai = OpenAIService()
        self.parser = AIResponseParser()
        self.repository = JDRepository()
    
    async def extract_jd(
        self,
        jd_text: str,
        request_id: str
    ) -> JDExtractionResult:
        """
        Extract JD data with automatic fallback
        Tries each service until one succeeds
        """
        services = [
            ("ollama", self.ollama, "Ollama"),
            ("gemini", self.gemini, "Gemini"),
            ("openai", self.openai, "OpenAI")
        ]
        
        last_error = None
        
        for service_type, service, service_name in services:
            try:
                logger.info(f"Attempting extraction with {service_name}")
                
                result = await self._extract_with_service(
                    service=service,
                    service_type=service_type,
                    service_name=service_name,
                    jd_text=jd_text,
                    request_id=request_id
                )
                
                if result:
                    logger.info(f"Successfully extracted with {service_name}")
                    return result
                    
            except AIExtractionError as e:
                last_error = e
                logger.warning(f"{service_name} extraction failed: {e}")
                
                # Log failure
                await self._log_failure(
                    request_id=request_id,
                    model_name=service_name,
                    model_type=service_type,
                    error_msg=str(e)
                )
                
                # Continue to next service
                continue
        
        # All services failed
        logger.error("All AI services failed")
        raise AIServiceUnavailableError(
            "All AI services unavailable",
            details={"last_error": str(last_error)}
        )
    
    async def _extract_with_service(
        self,
        service,
        service_type: str,
        service_name: str,
        jd_text: str,
        request_id: str
    ) -> Optional[JDExtractionResult]:
        """Extract using a specific service"""
        
        # Get raw response
        if service_type == "openai":
            raw_text, response_time, token_usage = await service.extract_jd(jd_text)
        else:
            raw_text, response_time = await service.extract_jd(jd_text)
            token_usage = {}
        
        # Parse response
        result = self.parser.parse_extraction_response(raw_text, service_name)
        result.ai_extraction_timestamp = datetime.utcnow()
        
        # Log success
        await self._log_success(
            request_id=request_id,
            model_name=service_name,
            model_type=service_type,
            response_time=response_time,
            token_usage=token_usage
        )
        
        return result
    
    async def _log_success(
        self,
        request_id: str,
        model_name: str,
        model_type: str,
        response_time: int,
        token_usage: dict
    ):
        """Log successful extraction"""
        audit_log = AIAuditLog(
            request_id=request_id,
            model_name=model_name,
            model_type=model_type,
            prompt_tokens=token_usage.get("prompt_tokens"),
            completion_tokens=token_usage.get("completion_tokens"),
            total_tokens=token_usage.get("total_tokens"),
            response_time_ms=response_time,
            status=ExtractionStatus.SUCCESS
        )
        
        await self.repository.save_audit_log(audit_log)
    
    async def _log_failure(
        self,
        request_id: str,
        model_name: str,
        model_type: str,
        error_msg: str
    ):
        """Log failed extraction attempt"""
        audit_log = AIAuditLog(
            request_id=request_id,
            model_name=model_name,
            model_type=model_type,
            response_time_ms=0,
            status=ExtractionStatus.FAILED,
            error_message=error_msg
        )
        
        await self.repository.save_audit_log(audit_log)
    
    async def health_check(self) -> dict:
        """Check health of all AI services"""
        return {
            "ollama": await self.ollama.health_check(),
            "gemini": await self.gemini.health_check(),
            "openai": await self.openai.health_check()
        }