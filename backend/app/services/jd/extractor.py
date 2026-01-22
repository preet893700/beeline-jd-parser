# app/services/jd/extractor.py
"""
JD Extraction Service
Orchestrates the extraction process

UPDATED: Split into sync and async background processing
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
from app.services.progress.tracker import progress_tracker

logger = logging.getLogger(__name__)

# Global cache for results (should be Redis in production)
_results_cache = {}
_excel_cache = {}


def get_cached_results(request_id: str):
    """Get cached results"""
    return _results_cache.get(request_id)


def get_cached_excel(request_id: str):
    """Get cached Excel file"""
    return _excel_cache.get(f"result_{request_id}")


class JDExtractor:
    """High-level JD extraction orchestration"""
    
    def __init__(self):
        self.ai_orchestrator = AIOrchestrator()
        self.excel_reader = ExcelReader()
        self.excel_exporter = ExcelExporter()
        self.repository = JDRepository()
    
    async def extract_from_excel_background(
        self,
        request_id: str,
        file_content: bytes,
        file_name: str,
        sheet_id: str,
        sheet_name: str,
        jd_column_index: int
    ):
        """
        Background task for extraction
        This runs asynchronously while frontend polls for progress
        """
        try:
            logger.info(
                f"Background extraction started: request_id={request_id}, "
                f"sheet_id={sheet_id}, sheet_name={sheet_name}, "
                f"column_index={jd_column_index}"
            )
            
            # Extract JD column data ONLY from specified sheet
            jd_texts = await self.excel_reader.extract_column_data(
                file_content,
                sheet_name,
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
            
            # START PROGRESS TRACKING
            non_empty_count = sum(1 for jd in jd_texts if jd.strip())
            progress_tracker.start_tracking(request_id, non_empty_count)
            
            # Process each JD
            results = []
            success_count = 0
            failure_count = 0
            
            for idx, jd_text in enumerate(jd_texts):
                if not jd_text.strip():
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
                
                finally:
                    # CRITICAL: Increment progress AFTER each record
                    progress_tracker.increment_progress(request_id)
            
            # Save results to database
            await self.repository.save_results(request_id, results)
            
            # Create Excel file with results
            excel_output = await self.excel_exporter.create_result_workbook(
                original_file=file_content,
                sheet_name=sheet_name,
                jd_column_index=jd_column_index,
                results=results
            )
            
            # Cache results for download
            _excel_cache[f"result_{request_id}"] = excel_output.getvalue()
            
            # Convert ExcelJDRow objects to dicts for JSON serialization
            results_dicts = [
                {
                    "row_index": r.row_index,
                    "original_jd": r.original_jd,
                    "extracted_data": r.extracted_data.model_dump()
                }
                for r in results
            ]
            
            _results_cache[request_id] = {
                "request_id": request_id,
                "results": results_dicts,
                "total_processed": len(results),
                "success_count": success_count,
                "failure_count": failure_count
            }
            
            logger.info(f"Cached results for request_id={request_id}")
            
            logger.info(
                f"Background extraction complete: request_id={request_id}, "
                f"sheet={sheet_name}, success={success_count}, failed={failure_count}"
            )
            
        except Exception as e:
            logger.error(f"Background extraction failed: {e}")
            # Mark as failed in progress tracker
            progress_tracker.stop_tracking(request_id)
    
    async def get_extraction_results(self, request_id: str):
        """Get cached results"""
        return _results_cache.get(request_id)
    
    async def get_excel_file(self, request_id: str):
        """Get cached Excel file"""
        return _excel_cache.get(f"result_{request_id}")
    
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