# app/repositories/jd_repository.py
"""
JD Repository
Database operations for JD parsing
"""

import logging
from typing import List, Optional
from datetime import datetime

from app.db.mongodb import MongoDBClient
from app.models.jd_result import (
    ExcelJDRequest,
    ExcelJDRow,
    JDExtractionResult,
    AIAuditLog
)
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class JDRepository:
    """Repository for JD data persistence"""
    
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        if self.db is None:
            self.db = MongoDBClient.get_database()
        return self.db
    
    async def save_request(self, request: ExcelJDRequest):
        """Save JD extraction request"""
        try:
            db = self._get_db()
            await db.jd_requests.insert_one(request.model_dump())
            logger.info(f"Saved request: {request.request_id}")
        except Exception as e:
            logger.error(f"Failed to save request: {e}")
            raise DatabaseError(f"Cannot save request: {str(e)}")
    
    async def save_results(self, request_id: str, results: List[ExcelJDRow]):
        """Save extraction results"""
        try:
            db = self._get_db()
            
            documents = []
            for result in results:
                doc = {
                    "request_id": request_id,
                    "row_index": result.row_index,
                    "original_jd": result.original_jd,
                    "extracted_data": result.extracted_data.model_dump(),
                    "created_at": datetime.utcnow()
                }
                documents.append(doc)
            
            if documents:
                await db.jd_results.insert_many(documents)
                logger.info(f"Saved {len(documents)} results for {request_id}")
                
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
            raise DatabaseError(f"Cannot save results: {str(e)}")
    
    async def save_text_result(
        self,
        request_id: str,
        jd_text: str,
        result: JDExtractionResult
    ):
        """Save text mode extraction result"""
        try:
            db = self._get_db()
            
            document = {
                "request_id": request_id,
                "jd_text": jd_text,
                "extracted_data": result.model_dump(),
                "created_at": datetime.utcnow()
            }
            
            await db.jd_results.insert_one(document)
            logger.info(f"Saved text result: {request_id}")
            
        except Exception as e:
            logger.error(f"Failed to save text result: {e}")
            raise DatabaseError(f"Cannot save text result: {str(e)}")
    
    async def save_audit_log(self, log: AIAuditLog):
        """Save AI service audit log"""
        try:
            db = self._get_db()
            await db.ai_audit_logs.insert_one(log.model_dump())
        except Exception as e:
            logger.error(f"Failed to save audit log: {e}")
            # Don't raise exception for audit logs
    
    async def get_results_by_request(
        self,
        request_id: str
    ) -> List[dict]:
        """Retrieve results by request ID"""
        try:
            db = self._get_db()
            cursor = db.jd_results.find({"request_id": request_id})
            results = await cursor.to_list(length=None)
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve results: {e}")
            raise DatabaseError(f"Cannot retrieve results: {str(e)}")
    
    async def get_audit_logs(
        self,
        request_id: Optional[str] = None,
        model_type: Optional[str] = None,
        limit: int = 100
    ) -> List[dict]:
        """Retrieve audit logs with filters"""
        try:
            db = self._get_db()
            
            query = {}
            if request_id:
                query["request_id"] = request_id
            if model_type:
                query["model_type"] = model_type
            
            cursor = db.ai_audit_logs.find(query).sort("timestamp", -1).limit(limit)
            logs = await cursor.to_list(length=limit)
            return logs
            
        except Exception as e:
            logger.error(f"Failed to retrieve audit logs: {e}")
            raise DatabaseError(f"Cannot retrieve audit logs: {str(e)}")