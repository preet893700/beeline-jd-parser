# app/db/mongodb.py
"""
MongoDB Database Client
Singleton pattern for connection management
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging

from app.core.config import settings
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class MongoDBClient:
    """MongoDB client singleton"""
    
    _client: Optional[AsyncIOMotorClient] = None
    _db: Optional[AsyncIOMotorDatabase] = None
    
    @classmethod
    async def connect(cls):
        """Establish MongoDB connection"""
        try:
            cls._client = AsyncIOMotorClient(settings.MONGODB_URL)
            cls._db = cls._client[settings.MONGODB_DB_NAME]
            
            # Test connection
            await cls._client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {settings.MONGODB_DB_NAME}")
            
            # Create indexes
            await cls._create_indexes()
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise DatabaseError(f"MongoDB connection failed: {str(e)}")
    
    @classmethod
    async def close(cls):
        """Close MongoDB connection"""
        if cls._client:
            cls._client.close()
            logger.info("MongoDB connection closed")
    
    @classmethod
    def get_database(cls) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if cls._db is None:
            raise DatabaseError("Database not initialized. Call connect() first.")
        return cls._db
    
    @classmethod
    async def _create_indexes(cls):
        """Create necessary database indexes"""
        db = cls.get_database()
        
        # JD Requests indexes
        await db.jd_requests.create_index("request_id", unique=True)
        await db.jd_requests.create_index("created_at")
        
        # JD Results indexes
        await db.jd_results.create_index("request_id")
        await db.jd_results.create_index("created_at")
        
        # AI Audit Logs indexes
        await db.ai_audit_logs.create_index("request_id")
        await db.ai_audit_logs.create_index("model_name")
        await db.ai_audit_logs.create_index("timestamp")
        
        logger.info("Database indexes created successfully")