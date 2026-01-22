import aiosqlite
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
import os

# Use Windows-compatible default paths
_default_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.getenv("DB_PATH", os.path.join(_default_data_dir, "contracts.db"))
DATA_DIR = os.getenv("DATA_DIR", _default_data_dir)

async def init_db():
    """Initialize the database"""
    os.makedirs(DATA_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                text_content TEXT,
                page_count INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS extracted_fields (
                document_id TEXT PRIMARY KEY,
                fields_json TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(document_id)
            )
        """)
        await db.commit()

async def close_db():
    """Close database connections"""
    pass

async def save_document(document_id: str, filename: str, text_content: str, 
                       metadata: Dict[str, Any], page_count: int):
    """Save document to database"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO documents 
            (document_id, filename, text_content, metadata, page_count)
            VALUES (?, ?, ?, ?, ?)
        """, (document_id, filename, text_content, json.dumps(metadata), page_count))
        await db.commit()

async def get_document(document_id: str) -> Optional[Dict[str, Any]]:
    """Get document from database"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT document_id, filename, uploaded_at, metadata, text_content, page_count
            FROM documents WHERE document_id = ?
        """, (document_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "document_id": row["document_id"],
                    "filename": row["filename"],
                    "uploaded_at": row["uploaded_at"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "text_content": row["text_content"],
                    "page_count": row["page_count"]
                }
    return None

async def save_extracted_fields(document_id: str, fields: Dict[str, Any]):
    """Save extracted fields to database"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO extracted_fields (document_id, fields_json)
            VALUES (?, ?)
        """, (document_id, json.dumps(fields)))
        await db.commit()

async def get_extracted_fields(document_id: str) -> Optional[Dict[str, Any]]:
    """Get extracted fields from database"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT fields_json FROM extracted_fields WHERE document_id = ?
        """, (document_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
    return None

async def list_documents() -> List[str]:
    """List all document IDs"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT document_id FROM documents") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

