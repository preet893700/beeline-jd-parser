# app/core/exceptions.py
"""
Custom Exception Classes
"""

class JDParserException(Exception):
    """Base exception for JD Parser"""
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class FileProcessingError(JDParserException):
    """Raised when file processing fails"""
    pass


class ExcelReadError(FileProcessingError):
    """Raised when Excel file cannot be read"""
    pass


class AIExtractionError(JDParserException):
    """Raised when AI extraction fails"""
    pass


class AIServiceUnavailableError(AIExtractionError):
    """Raised when all AI services are unavailable"""
    pass


class DatabaseError(JDParserException):
    """Raised when database operations fail"""
    pass


class ValidationError(JDParserException):
    """Raised when data validation fails"""
    pass