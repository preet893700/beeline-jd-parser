# app/services/jd/extractor.py
"""
JD Extraction Service
Orchestrates the extraction process
"""

import logging
import uuid
from typing import List
from datetime import datetime

from app.models.jd_result import (
    ExcelJDRow,
    ExcelJDResponse,
    JDExtractionResult,
    ExcelJDRequest
)
from app.services.ai.orchestrator import AIOrchestrator
from app.services.excel.reader import ExcelReader
from app.services.excel.exporter import ExcelExporter
from app.repositories.jd_repository import JDRepository
from app.core.exceptions import AIExtractionError

logger = logging.getLogger(__name__)


class JDExtractor:
    """High-level JD extraction orchestration"""
    
    def __init__(self):
        self.ai_orchestrator = AIOrchestrator()
        self.excel_reader = ExcelReader()
        self.excel_exporter = ExcelExporter()
        self.repository = JDRepository()
    
    async def extract_from_excel(
        self,
        file_content: bytes,
        file_name: str,
        sheet_id: str,
        sheet_name: str,
        jd_column_index: int
    ) -> tuple[ExcelJDResponse, bytes]:
        """
        Extract JDs from Excel file
        
        CRITICAL: Only processes the specified sheet
        - sheet_id: Unique identifier for the sheet
        - sheet_name: Display name of the sheet
        - jd_column_index: Column containing JD text
        
        Returns: (response, excel_file_bytes)
        """
        request_id = str(uuid.uuid4())
        
        logger.info(
            f"Starting Excel extraction: request_id={request_id}, "
            f"sheet_id={sheet_id}, sheet_name={sheet_name}, "
            f"column_index={jd_column_index}"
        )
        
        # CRITICAL: Extract JD column data ONLY from specified sheet
        jd_texts = await self.excel_reader.extract_column_data(
            file_content,
            sheet_name,  # Use sheet_name for openpyxl compatibility
            jd_column_index
        )
        
        # Get column header for audit trail
        preview_data = await self.excel_reader.read_file(file_content)
        matching_sheet = next((s for s in preview_data["sheets"] if s["id"] == sheet_id), None)
        column_header = matching_sheet["headers"][jd_column_index] if matching_sheet else "Unknown"
        
        # Save request metadata
        request = ExcelJDRequest(
            request_id=request_id,
            file_name=file_name,
            sheet_id=sheet_id,
            sheet_name=sheet_name,
            jd_column_index=jd_column_index,
            jd_column_header=column_header,
            total_rows=len(jd_texts)
        )
        await self.repository.save_request(request)
        
        # Process each JD
        results = []
        success_count = 0
        failure_count = 0
        
        for idx, jd_text in enumerate(jd_texts):
            if not jd_text.strip():
                # Skip empty cells
                continue
            
            try:
                extracted = await self.ai_orchestrator.extract_jd(
                    jd_text=jd_text,
                    request_id=request_id
                )
                
                results.append(ExcelJDRow(
                    row_index=idx,
                    original_jd=jd_text,
                    extracted_data=extracted
                ))
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to extract row {idx}: {e}")
                failure_count += 1
        
        # Create response
        response = ExcelJDResponse(
            request_id=request_id,
            results=results,
            total_processed=len(results),
            success_count=success_count,
            failure_count=failure_count
        )
        
        # Save results
        await self.repository.save_results(request_id, results)
        
        # Create Excel file with results - ONLY for the specified sheet
        excel_output = await self.excel_exporter.create_result_workbook(
            original_file=file_content,
            sheet_name=sheet_name,
            jd_column_index=jd_column_index,
            results=results
        )
        
        logger.info(
            f"Extraction complete: request_id={request_id}, "
            f"sheet={sheet_name}, success={success_count}, failed={failure_count}"
        )
        
        return response, excel_output.getvalue()
    
    async def extract_from_text(
        self,
        jd_text: str
    ) -> JDExtractionResult:
        """Extract from single text JD"""
        request_id = str(uuid.uuid4())
        
        logger.info(f"Starting text extraction: {request_id}")
        
        result = await self.ai_orchestrator.extract_jd(
            jd_text=jd_text,
            request_id=request_id
        )
        
        # Save to database
        await self.repository.save_text_result(request_id, jd_text, result)
        
        return result