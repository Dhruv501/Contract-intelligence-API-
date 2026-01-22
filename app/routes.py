from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query, Body
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List, Optional
from pydantic import BaseModel
import asyncio
import json
import uuid

from app.database import save_document, get_document, get_extracted_fields, save_extracted_fields, list_documents
from app.pdf_processor import extract_text_from_pdf, generate_document_id
from app.extractor import extract_structured_fields
from app.rag import rag
from app.auditor import auditor
from app.metrics import metrics
from app.webhook import emit_webhook_event

router = APIRouter()

class ExtractRequest(BaseModel):
    document_id: str

class AskRequest(BaseModel):
    question: str
    document_ids: Optional[List[str]] = None

class AuditRequest(BaseModel):
    document_id: str

@router.post("/ingest")
async def ingest_documents(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None
):
    """Ingest one or more PDF documents"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    document_ids = []
    
    for file in files:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")
        
        content = await file.read()
        
        try:
            text_content, page_count, metadata = extract_text_from_pdf(content)
            document_id = generate_document_id(file.filename, content)
            
            await save_document(
                document_id=document_id,
                filename=file.filename,
                text_content=text_content,
                metadata=metadata,
                page_count=page_count
            )
            
            document_ids.append(document_id)
            metrics.increment("documents_ingested")
            
            if background_tasks:
                background_tasks.add_task(
                    emit_webhook_event,
                    "document.ingested",
                    {"document_id": document_id, "filename": file.filename}
                )
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing {file.filename}: {str(e)}")
    
    return {
        "document_ids": document_ids,
        "count": len(document_ids)
    }

@router.post("/extract")
async def extract_fields(
    request: ExtractRequest,
    background_tasks: BackgroundTasks = None
):
    """Extract structured fields from a document"""
    document_id = request.document_id
    
    existing = await get_extracted_fields(document_id)
    if existing:
        return existing
    
    doc = await get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    text = doc["text_content"]
    fields = extract_structured_fields(text)
    
    await save_extracted_fields(document_id, fields)
    metrics.increment("extractions_performed")
    
    if background_tasks:
        background_tasks.add_task(
            emit_webhook_event,
            "document.extracted",
            {"document_id": document_id}
        )
    
    return fields

@router.post("/ask")
async def ask_question(
    request: AskRequest
):
    """Ask a question about the documents using RAG"""
    if not request.question:
        raise HTTPException(status_code=400, detail="Question is required")
    
    result = await rag.answer_question(request.question, request.document_ids)
    metrics.increment("questions_asked")
    
    return result

@router.get("/ask/stream")
async def ask_question_stream(
    question: str = Query(..., description="The question to ask"),
    document_ids: Optional[List[str]] = Query(None, description="Specific document IDs to query")
):
    """Stream answer tokens using Server-Sent Events"""
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    
    async def generate_stream():
        result = await rag.answer_question(question, document_ids)
        answer = result["answer"]
        citations = result["citations"]
        
        words = answer.split()
        for word in words:
            yield f"data: {json.dumps({'token': word + ' ', 'done': False})}\n\n"
            await asyncio.sleep(0.05)
        
        yield f"data: {json.dumps({'citations': citations, 'done': True})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/audit")
async def audit_document(
    request: AuditRequest,
    background_tasks: BackgroundTasks = None
):
    """Audit a document for risky clauses"""
    document_id = request.document_id
    doc = await get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    findings = await auditor.audit_document(document_id)
    metrics.increment("audits_performed")
    
    if background_tasks:
        background_tasks.add_task(
            emit_webhook_event,
            "document.audited",
            {"document_id": document_id, "findings_count": len(findings)}
        )
    
    return {
        "document_id": document_id,
        "findings": findings,
        "count": len(findings)
    }

@router.post("/webhook/events")
async def webhook_events(
    event_type: str = Body(...),
    payload: dict = Body(None)
):
    """Webhook endpoint for receiving events"""
    return {
        "status": "received",
        "event_type": event_type,
        "payload": payload
    }


