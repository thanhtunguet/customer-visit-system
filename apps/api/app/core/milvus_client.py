from __future__ import annotations

import logging
import os
import warnings
from typing import Dict, List, Optional

from .config import settings

logger = logging.getLogger(__name__)

# Try to import pymilvus, fallback to mock if not available
try:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=UserWarning, message="pkg_resources is deprecated.*"
        )
        from pymilvus import (
            Collection,
            CollectionSchema,
            DataType,
            FieldSchema,
            connections,
            utility,
        )
    MILVUS_AVAILABLE = True
except Exception as e:
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
        self.is_connected = False

    async def connect(self):
        """Connect to Milvus server"""
        if not MILVUS_AVAILABLE:
            logger.info("Using mock Milvus implementation for development")
            self.collection = Collection("mock_collection")
            self.is_connected = True
            return

        try:
            # Enhanced connection with additional parameters for production
            connect_params = {
                "alias": self.connection_alias,
                "host": settings.milvus_host,
                "port": settings.milvus_port,
            }

            # Add optional authentication if configured
            milvus_user = os.getenv("MILVUS_USER")
            milvus_password = os.getenv("MILVUS_PASSWORD")
            if milvus_user and milvus_password:
                connect_params.update(
                    {"user": milvus_user, "password": milvus_password}
                )
                logger.info(
                    f"Connecting to Milvus at {settings.milvus_host}:{settings.milvus_port} with authentication"
                )
            else:
                logger.info(
                    f"Connecting to Milvus at {settings.milvus_host}:{settings.milvus_port} without authentication"
                )

            # Add SSL support if configured
            milvus_secure = os.getenv("MILVUS_SECURE", "false").lower() == "true"
            if milvus_secure:
                connect_params["secure"] = True
                logger.info("Using secure connection to Milvus")

            connections.connect(**connect_params)
            await self._ensure_collection_exists()
            self.is_connected = True
            logger.info(
                f"Successfully connected to Milvus at {settings.milvus_host}:{settings.milvus_port}"
            )
        except Exception as e:
            logger.error(
                f"Failed to connect to Milvus: {e}. Using mock implementation."
            )
            self.collection = Collection("mock_collection")
            self.is_connected = False

    async def disconnect(self):
        """Disconnect from Milvus"""
        if not self.is_connected:
            return

        try:
            if MILVUS_AVAILABLE:
                connections.disconnect(alias=self.connection_alias)
            self.is_connected = False
            self.collection = None
            logger.info("Disconnected from Milvus")
        except Exception as e:
            logger.warning(f"Error disconnecting from Milvus: {e}")
            self.is_connected = False

    async def health_check(self) -> Dict[str, any]:
        """Check Milvus connection health"""
        try:
            if not MILVUS_AVAILABLE:
                return {
                    "status": "mock",
                    "message": "Using mock Milvus implementation",
                    "connected": True,
                }

            if not self.is_connected:
                return {
                    "status": "disconnected",
                    "message": "Not connected to Milvus",
                    "connected": False,
                }

            # Try to list collections as a health check
            collections = utility.list_collections(using=self.connection_alias)

            return {
                "status": "healthy",
                "message": f"Connected to Milvus at {settings.milvus_host}:{settings.milvus_port}",
                "connected": True,
                "collection_exists": self.collection_name in collections,
                "collections_count": len(collections),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "connected": False,
            }

    async def _ensure_collection_exists(self):
        """Create collection if it doesn't exist or recreate if schema is wrong"""
        if not MILVUS_AVAILABLE:
            return

        # Define the expected schema
        expected_fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="person_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="person_type", dtype=DataType.VARCHAR, max_length=16),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=512),
            FieldSchema(name="created_at", dtype=DataType.INT64),
        ]
        schema = CollectionSchema(
            expected_fields, description="Face embeddings for recognition"
        )

        # Check if collection exists
        if utility.has_collection(self.collection_name, using=self.connection_alias):
            try:
                # Load existing collection and check its schema
                existing_collection = Collection(
                    self.collection_name, using=self.connection_alias
                )
                existing_fields = existing_collection.schema.fields

                # Get field names from existing schema
                existing_field_names = [field.name for field in existing_fields]
                expected_field_names = [field.name for field in expected_fields]

                # Check if schema matches
                if set(existing_field_names) != set(expected_field_names):
                    logger.warning(
                        f"Collection {self.collection_name} exists but has wrong schema. Dropping and recreating..."
                    )
                    logger.info(f"Existing fields: {existing_field_names}")
                    logger.info(f"Expected fields: {expected_field_names}")

                    # Drop the existing collection
                    utility.drop_collection(
                        self.collection_name, using=self.connection_alias
                    )
                    logger.info(f"Dropped existing collection: {self.collection_name}")
                else:
                    # Schema matches, use existing collection
                    self.collection = existing_collection
                    self.collection.load()
                    logger.info(
                        f"Using existing Milvus collection: {self.collection_name}"
                    )
                    return

            except Exception as e:
                logger.warning(
                    f"Error checking existing collection schema: {e}. Dropping and recreating..."
                )
                try:
                    utility.drop_collection(
                        self.collection_name, using=self.connection_alias
                    )
                except Exception:
                    pass  # Collection might not exist or be accessible

        # Create new collection
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

        logger.info(f"Created new Milvus collection: {self.collection_name}")

        self.collection = collection
        self.collection.load()

    async def reset_collection(self):
        """Drop and recreate the collection - useful for development"""
        if not MILVUS_AVAILABLE:
            logger.info("Milvus not available, using mock implementation")
            return

        try:
            if utility.has_collection(
                self.collection_name, using=self.connection_alias
            ):
                utility.drop_collection(
                    self.collection_name, using=self.connection_alias
                )
                logger.info(f"Dropped collection: {self.collection_name}")

            await self._ensure_collection_exists()
            logger.info(f"Collection reset completed: {self.collection_name}")

        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            raise

    async def insert_embedding(
        self,
        tenant_id: int,
        person_id: int,
        person_type: str,
        embedding: List[float],
        created_at: int,
    ) -> str:
        """Insert a face embedding"""
        if not self.collection:
            raise RuntimeError("Not connected to Milvus")

        # For Milvus, data should be provided as a list of dictionaries or as column-wise data
        # Since we have auto_id=True for the 'id' field, we shouldn't include it
        # Convert IDs to strings to match the VARCHAR schema
        data = [
            {
                "tenant_id": str(tenant_id),
                "person_id": str(person_id),
                "person_type": person_type,
                "embedding": embedding,
                "created_at": created_at,
            }
        ]

        result = self.collection.insert(data)
        self.collection.flush()

        return str(result.primary_keys[0])

    async def search_similar_faces(
        self,
        tenant_id: int,
        embedding: List[float],
        limit: int = 5,
        threshold: float = 0.6,
    ) -> List[Dict]:
        """Search for similar face embeddings within a tenant"""
        if not self.collection:
            raise RuntimeError("Not connected to Milvus")

        # Enhanced logging for debugging
        logger.info(
            f"Searching for similar faces: tenant_id={tenant_id}, threshold={threshold}, limit={limit}"
        )

        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 16},  # Increased nprobe for better search quality
        }

        # Search with tenant filter - convert tenant_id to string for VARCHAR schema
        expr = f'tenant_id == "{str(tenant_id)}"'
        logger.debug(f"Milvus search expression: {expr}")

        try:
            results = self.collection.search(
                data=[embedding],
                anns_field="embedding",
                param=search_params,
                limit=limit * 2,  # Get more results for better filtering
                expr=expr,
                output_fields=["tenant_id", "person_id", "person_type", "created_at"],
            )
        except Exception as e:
            logger.error(f"Milvus search failed: {e}")
            return []

        matches = []
        if results and len(results[0]) > 0:
            logger.info(f"Milvus returned {len(results[0])} raw results")

            for hit in results[0]:
                similarity_score = float(hit.score)

                # Apply strict threshold filtering
                if similarity_score >= threshold:
                    # Convert person_id back to int for consistency
                    person_id_str = hit.entity.get("person_id")
                    person_id = (
                        int(person_id_str)
                        if person_id_str and person_id_str.isdigit()
                        else person_id_str
                    )
                    person_type = hit.entity.get("person_type")

                    match_entry = {
                        "person_id": person_id,
                        "person_type": person_type,
                        "similarity": similarity_score,
                        "id": str(hit.id),
                        "created_at": hit.entity.get("created_at"),
                    }
                    matches.append(match_entry)

                    logger.debug(
                        f"Valid match: {person_type} {person_id} with similarity {similarity_score:.3f}"
                    )
                else:
                    logger.debug(
                        f"Below threshold match: {similarity_score:.3f} < {threshold}"
                    )

        # Sort by similarity and limit results
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        final_matches = matches[:limit]

        logger.info(
            f"Returning {len(final_matches)} filtered matches (threshold >= {threshold})"
        )
        for match in final_matches:
            logger.info(
                f"  - {match['person_type']} {match['person_id']}: {match['similarity']:.3f}"
            )

        return final_matches

    async def delete_person_embeddings(
        self, tenant_id: int, person_id: int, person_type: str = None
    ):
        """Delete all embeddings for a person.

        Args:
            tenant_id: The tenant ID
            person_id: The person ID
            person_type: Optional person type filter ("customer", "staff")

        Some Milvus deployments restrict delete operations to primary key filters only.
        To support that, we first query for primary keys matching the tenant/person,
        then delete using an "id in [...]" expression.
        """
        if not self.collection:
            raise RuntimeError("Not connected to Milvus")

        try:
            # Query for primary keys of matching records - convert IDs to strings for VARCHAR schema
            query_expr = (
                f'tenant_id == "{str(tenant_id)}" && person_id == "{str(person_id)}"'
            )
            if person_type:
                query_expr += f' && person_type == "{person_type}"'

            rows = []
            try:
                # Prefer query API to fetch primary keys
                rows = self.collection.query(expr=query_expr, output_fields=["id"])  # type: ignore[attr-defined]
            except Exception as e:
                logger.warning(
                    f"Milvus query not available or failed during delete lookup: {e}"
                )

            primary_keys: List[int] = []
            if rows:
                for row in rows:
                    pk = row.get("id")
                    if pk is not None:
                        try:
                            primary_keys.append(int(pk))
                        except Exception:
                            pass

            if primary_keys:
                pk_list = ",".join(str(pk) for pk in primary_keys)
                delete_expr = f"id in [{pk_list}]"
                self.collection.delete(delete_expr)
                self.collection.flush()
                logger.info(
                    f"Deleted {len(primary_keys)} embeddings for {person_type or 'person'} {person_id}"
                )
            else:
                # Nothing to delete, or query unsupported
                logger.info(
                    "No existing embeddings found for deletion (tenant_id=%s, person_id=%s, person_type=%s)",
                    tenant_id,
                    person_id,
                    person_type,
                )

        except Exception as e:
            # Do not hard-fail embedding recalculation due to delete limitations
            logger.error(
                f"Failed to delete existing embeddings for tenant_id={tenant_id}, person_id={person_id}, person_type={person_type}: {e}"
            )

    async def delete_face_embedding(self, tenant_id: str, visit_id: str):
        """Delete face embedding by visit_id (uses metadata approach)

        Since current Milvus schema doesn't include visit_id,
        this is a placeholder for future implementation.
        In the current system, we rely on database cleanup to handle this.
        """
        if not self.collection:
            raise RuntimeError("Not connected to Milvus")

        # Current limitation: Milvus schema doesn't include visit_id
        # For now, we'll log this action but cannot delete specific visit embeddings
        # In a future version, the schema should include visit_id as a field
        logger.warning(
            f"delete_face_embedding called for visit_id={visit_id}, but current Milvus schema doesn't support visit_id filtering"
        )

        # TODO: Enhance Milvus schema to include visit_id field for precise deletion
        # For now, the database cleanup will handle visit removal, and orphaned embeddings
        # will be cleaned up through periodic maintenance jobs

    async def delete_embedding_by_metadata(self, tenant_id: int, metadata_filter: Dict):
        """Delete embeddings by metadata filter - simplified to delete by person_id"""
        if not self.collection:
            raise RuntimeError("Not connected to Milvus")

        # Since we don't have metadata support in the current schema,
        # we'll just log a warning and not delete anything for now
        # In production, you'd want to store metadata and use it for deletion
        logger.warning(
            f"delete_embedding_by_metadata called with filter {metadata_filter}, but metadata is not supported in current schema"
        )
        # For now, we'll ignore this operation to avoid errors


# Global Milvus client instance
milvus_client = MilvusClient()
