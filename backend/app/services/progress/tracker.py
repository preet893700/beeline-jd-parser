# app/services/progress/tracker.py
"""
Simple In-Memory Progress Tracker
Thread-safe progress tracking for extraction requests

CRITICAL: This is Step-1 implementation
- In-memory only (no DB, no Redis)
- Thread-safe with locks
- Auto-cleanup to prevent memory leaks
"""

import threading
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ProgressState:
    """Progress state for a single request"""
    
    def __init__(self, request_id: str, total_records: int):
        self.request_id = request_id
        self.total_records = total_records
        self.processed_records = 0
        self.created_at = datetime.utcnow()
        self._lock = threading.Lock()
    
    def increment(self):
        """Thread-safe increment of processed count"""
        with self._lock:
            self.processed_records += 1
            logger.debug(f"Progress: {self.request_id} -> {self.processed_records}/{self.total_records}")
    
    def get_progress(self) -> Dict[str, int]:
        """Get current progress snapshot"""
        with self._lock:
            return {
                "total": self.total_records,
                "processed": self.processed_records
            }
    
    def is_complete(self) -> bool:
        """Check if processing is complete"""
        with self._lock:
            return self.processed_records >= self.total_records


class ProgressTracker:
    """
    Global progress tracker singleton
    Manages progress for all active extraction requests
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize tracker state"""
        self._progress_states: Dict[str, ProgressState] = {}
        self._cleanup_lock = threading.Lock()
    
    def start_tracking(self, request_id: str, total_records: int) -> None:
        """
        Start tracking progress for a request
        
        Args:
            request_id: Unique request identifier
            total_records: Total number of records to process
        """
        with self._cleanup_lock:
            self._progress_states[request_id] = ProgressState(request_id, total_records)
            logger.info(f"Started tracking: {request_id} with {total_records} records")
    
    def increment_progress(self, request_id: str) -> None:
        """
        Increment processed count for a request
        Call this after each record is processed (success OR failure)
        
        Args:
            request_id: Request identifier
        """
        state = self._progress_states.get(request_id)
        if state:
            state.increment()
        else:
            logger.warning(f"No progress state found for: {request_id}")
    
    def get_progress(self, request_id: str) -> Optional[Dict[str, int]]:
        """
        Get current progress for a request
        
        Args:
            request_id: Request identifier
            
        Returns:
            {"total": int, "processed": int} or None if not found
        """
        state = self._progress_states.get(request_id)
        if state:
            return state.get_progress()
        return None
    
    def stop_tracking(self, request_id: str) -> None:
        """
        Stop tracking and cleanup state
        
        Args:
            request_id: Request identifier
        """
        with self._cleanup_lock:
            if request_id in self._progress_states:
                del self._progress_states[request_id]
                logger.info(f"Stopped tracking: {request_id}")
    
    def cleanup_old_states(self, max_age_minutes: int = 60) -> None:
        """
        Cleanup progress states older than max_age_minutes
        Call this periodically to prevent memory leaks
        
        Args:
            max_age_minutes: Maximum age of progress state in minutes
        """
        with self._cleanup_lock:
            cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)
            to_remove = [
                request_id
                for request_id, state in self._progress_states.items()
                if state.created_at < cutoff_time
            ]
            
            for request_id in to_remove:
                del self._progress_states[request_id]
                logger.info(f"Cleaned up old progress state: {request_id}")
            
            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} old progress states")


# Global tracker instance
progress_tracker = ProgressTracker()