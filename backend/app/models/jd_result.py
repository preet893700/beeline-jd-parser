# app/models/jd_result.py
"""
Data Models for JD Extraction
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ExtractionStatus(str, Enum):
    """AI extraction status"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class JDExtractionResult(BaseModel):
    """Structured JD extraction result"""
    bill_rate: Optional[str] = None
    duration: Optional[str] = None
    experience_required: Optional[str] = None
    gbams_rgs_id: Optional[str] = None
    ai_location: Optional[str] = None
    skills: Optional[List[str]] = None
    role_description: Optional[str] = None
    msp_owner: Optional[str] = None
    
    # AI metadata
    ai_model_used: Optional[str] = None
    ai_extraction_status: Optional[ExtractionStatus] = None
    ai_extraction_timestamp: Optional[datetime] = None


class ExcelJDRequest(BaseModel):
    """Request model for Excel JD extraction"""
    request_id: str
    file_name: str
    sheet_id: str  # CRITICAL: Unique sheet identifier
    sheet_name: str
    jd_column_index: int
    jd_column_header: str  # CRITICAL: Column header for audit trail
    total_rows: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExcelJDRow(BaseModel):
    """Single row extraction result for Excel mode"""
    row_index: int
    original_jd: str
    extracted_data: JDExtractionResult


class ExcelJDResponse(BaseModel):
    """Response model for Excel JD extraction"""
    request_id: str
    results: List[ExcelJDRow]
    total_processed: int
    success_count: int
    failure_count: int


class TextJDRequest(BaseModel):
    """Request model for text JD extraction"""
    jd_text: str


class TextJDResponse(JDExtractionResult):
    """Response model for text JD extraction"""
    pass


class AIAuditLog(BaseModel):
    """AI service audit log"""
    request_id: str
    model_name: str
    model_type: str  # ollama, gemini, openai
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    response_time_ms: int
    status: ExtractionStatus
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)