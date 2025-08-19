from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .config import settings

logger = logging.getLogger(__name__)

# Try to import pymilvus, fallback to mock if not available
try:
    from pymilvus import Collection, DataType, FieldSchema, CollectionSchema, connections, utility
    MILVUS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Milvus not available: {e}. Using mock implementation.")
    MILVUS_AVAILABLE = False
    
    # Mock classes for development
    class Collection:
        def __init__(self, *args, **kwargs):
            pass
        def load(self):
            pass
        def insert(self, data):
            class MockResult:
                primary_keys = ["mock_id_123"]
            return MockResult()
        def search(self, *args, **kwargs):
            return [[]]  # Empty search results
        def delete(self, expr):
            pass
        def flush(self):
            pass
    
    class DataType:
        INT64 = "INT64"
        VARCHAR = "VARCHAR"
        FLOAT_VECTOR = "FLOAT_VECTOR"
    
    class FieldSchema:
        def __init__(self, *args, **kwargs):
            pass
    
    class CollectionSchema:
        def __init__(self, *args, **kwargs):
            pass
    
    class connections:
        @staticmethod
        def connect(*args, **kwargs):
            pass
        @staticmethod
        def disconnect(*args, **kwargs):
            pass
    
    class utility:
        @staticmethod
        def has_collection(*args, **kwargs):
            return False

logger = logging.getLogger(__name__)


class MilvusClient:
    def __init__(self):
        self.collection_name = settings.milvus_collection
        self.connection_alias = "default"
        self.collection: Optional[Collection] = None
        
    async def connect(self):
        """Connect to Milvus server"""
        if not MILVUS_AVAILABLE:
            logger.info("Using mock Milvus implementation for development")
            self.collection = Collection("mock_collection")
            return
            
        try:
            connections.connect(
                alias=self.connection_alias,
                host=settings.milvus_host,
                port=settings.milvus_port,
            )
            await self._ensure_collection_exists()
            logger.info(f"Connected to Milvus at {settings.milvus_host}:{settings.milvus_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}. Using mock implementation.")
            self.collection = Collection("mock_collection")

    async def disconnect(self):
        """Disconnect from Milvus"""
        try:
            connections.disconnect(alias=self.connection_alias)
        except Exception as e:
            logger.warning(f"Error disconnecting from Milvus: {e}")

    async def _ensure_collection_exists(self):
        """Create collection if it doesn't exist"""
        if not MILVUS_AVAILABLE:
            return
            
        if not utility.has_collection(self.collection_name, using=self.connection_alias):
            # Define schema
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="person_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="person_type", dtype=DataType.VARCHAR, max_length=16),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=512),
                FieldSchema(name="created_at", dtype=DataType.INT64),
            ]
            schema = CollectionSchema(fields, description="Face embeddings for recognition")
            
            # Create collection
            collection = Collection(
                name=self.collection_name,
                schema=schema,
                using=self.connection_alias,
            )
            
            # Create index
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024},
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            
            logger.info(f"Created Milvus collection: {self.collection_name}")
        
        self.collection = Collection(self.collection_name, using=self.connection_alias)
        self.collection.load()

    async def insert_embedding(
        self,
        tenant_id: str,
        person_id: str,
        person_type: str,
        embedding: List[float],
        created_at: int,
    ) -> str:
        """Insert a face embedding"""
        if not self.collection:
            raise RuntimeError("Not connected to Milvus")
            
        data = [
            [tenant_id],
            [person_id],
            [person_type],
            [embedding],
            [created_at],
        ]
        
        result = self.collection.insert(data)
        self.collection.flush()
        
        return str(result.primary_keys[0])

    async def search_similar_faces(
        self,
        tenant_id: str,
        embedding: List[float],
        limit: int = 5,
        threshold: float = 0.6,
    ) -> List[Dict]:
        """Search for similar face embeddings within a tenant"""
        if not self.collection:
            raise RuntimeError("Not connected to Milvus")

        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 10},
        }

        # Search with tenant filter
        expr = f'tenant_id == "{tenant_id}"'
        
        results = self.collection.search(
            data=[embedding],
            anns_field="embedding",
            param=search_params,
            limit=limit,
            expr=expr,
            output_fields=["tenant_id", "person_id", "person_type", "created_at"],
        )

        matches = []
        if results and len(results[0]) > 0:
            for hit in results[0]:
                if hit.score >= threshold:
                    matches.append({
                        "person_id": hit.entity.get("person_id"),
                        "person_type": hit.entity.get("person_type"),
                        "similarity": float(hit.score),
                        "id": str(hit.id),
                    })

        return matches

    async def delete_person_embeddings(self, tenant_id: str, person_id: str):
        """Delete all embeddings for a person"""
        if not self.collection:
            raise RuntimeError("Not connected to Milvus")
            
        expr = f'tenant_id == "{tenant_id}" && person_id == "{person_id}"'
        self.collection.delete(expr)
        self.collection.flush()


# Global Milvus client instance
milvus_client = MilvusClient()