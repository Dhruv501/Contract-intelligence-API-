# Contract Intelligence API

A production-ready FastAPI service for ingesting, extracting, analyzing, and querying contract documents using PDF processing, structured field extraction, RAG (Retrieval-Augmented Generation), and risk auditing.

## Features

- **PDF Ingestion**: Upload and process multiple PDF documents
- **Structured Field Extraction**: Automatically extract key contract fields (parties, dates, terms, etc.)
- **Question Answering**: Ask questions about contracts with citations using LLM or simple extraction
- **Risk Auditing**: Detect risky clauses (auto-renewal, unlimited liability, etc.)
- **Streaming Responses**: Server-Sent Events for streaming answers
- **Webhook Support**: Optional webhook events for long-running tasks
- **Metrics & Health**: Built-in metrics and health check endpoints
- **LLM Integration**: Supports Ollama (local)

## Quick Start

### Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd contract_intelligence_api
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server:**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Access the API:**
   - API: http://localhost:8000
   - Interactive Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/healthz

### Docker Setup

```bash
docker-compose up --build
```

## LLM Configuration 

The API supports multiple LLM providers for enhanced question answering:

### Ollama (Recommended)

1. Install Ollama from https://ollama.ai
2. Download a model:
   ```bash
   ollama pull llama2
   ```
3. The API will automatically use Ollama if available


### Disable LLM

```bash
export LLM_ENABLED="false"
```

## API Endpoints

### POST `/ingest`
Upload one or more PDF documents.

**Request:** Multipart form data with PDF files

**Response:**
```json
{
  "document_ids": ["20240101120000_abc123"],
  "count": 1
}
```

### POST `/extract`
Extract structured fields from a document.

**Request:**
```json
{
  "document_id": "20240101120000_abc123"
}
```

**Response:**
```json
{
  "parties": ["Company A", "Company B"],
  "effective_date": "2024-01-01",
  "term": "2 years",
  "governing_law": "State of California",
  "payment_terms": "Net 30",
  "termination": "Either party may terminate with 30 days notice",
  "auto_renewal": "Automatically renews for 1 year unless terminated",
  "confidentiality": "Both parties agree to maintain confidentiality",
  "indemnity": "Each party shall indemnify the other",
  "liability_cap": {
    "amount": "$100,000",
    "currency": "USD"
  },
  "signatories": [
    {
      "name": "John Doe",
      "title": "CEO"
    }
  ]
}
```

### POST `/ask`
Ask questions about uploaded documents.

**Request:**
```json
{
  "question": "What is the effective date?",
  "document_ids": null
}
```

**Response:**
```json
{
  "answer": "Based on the document, the effective date is: 2024-01-01",
  "citations": [
    {
      "document_id": "20240101120000_abc123",
      "page": 1,
      "char_range": [100, 200],
      "text_snippet": "This agreement is effective as of January 1, 2024..."
    }
  ]
}
```

### GET `/ask/stream`
Stream answer tokens using Server-Sent Events.

**Query Parameters:**
- `question`: The question to ask
- `document_ids`: (Optional) List of document IDs

### POST `/audit`
Audit a document for risky clauses.

**Request:**
```json
{
  "document_id": "20240101120000_abc123"
}
```

**Response:**
```json
{
  "document_id": "20240101120000_abc123",
  "findings": [
    {
      "risk_type": "auto_renewal_short_notice",
      "severity": "high",
      "description": "Auto-renewal clause with less than 30 days notice period",
      "evidence": "This agreement shall automatically renew unless terminated with 15 days notice...",
      "char_range": [500, 600],
      "page": 3,
      "document_id": "20240101120000_abc123"
    }
  ],
  "count": 1
}
```

### GET `/healthz`
Health check endpoint.

### GET `/metrics`
Get service metrics.

### GET `/docs`
Interactive Swagger/OpenAPI documentation.

## Environment Variables

- `DB_PATH`: Path to SQLite database (default: `./data/contracts.db`)
- `DATA_DIR`: Directory for data storage (default: `./data`)
- `WEBHOOK_URL`: Optional webhook URL for event emission
- `LLM_ENABLED`: Enable/disable LLM (default: `true`)
- `LLM_PROVIDER`: LLM provider - `ollama`, `groq`, `huggingface`, `openai`, or `none` (default: `ollama`)
- `OLLAMA_URL`: Ollama server URL (default: `http://localhost:11434`)
- `OLLAMA_MODEL`: Ollama model name (default: `llama2`)

## Project Structure

```
contract_intelligence_api/
├── app/
│   ├── __init__.py
│   ├── routes.py          # API route handlers
│   ├── database.py        # SQLite database operations
│   ├── pdf_processor.py   # PDF text extraction
│   ├── extractor.py       # Structured field extraction
│   ├── rag.py            # RAG implementation for Q&A
│   ├── auditor.py         # Risk detection/auditing
│   ├── metrics.py        # Metrics collection
│   └── webhook.py        # Webhook event emission
├── main.py               # FastAPI application entry point
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Docker Compose configuration
├── .gitignore          # Git ignore patterns
└── README.md           # This file
```

## Architecture

- **FastAPI**: Modern, fast web framework
- **SQLite (aiosqlite)**: Lightweight database for document storage
- **PyPDF2 & pdfplumber**: PDF text extraction
- **Regex-based Extraction**: Pattern matching for structured fields
- **RAG with LLM**: Text chunking, search, and LLM-based answer generation
- **Rule-based Auditing**: Pattern matching for risk detection

## Development

### Running Tests

The API includes interactive documentation at `/docs` for testing endpoints.

### Memory Management

The system includes safeguards for large documents:
- Maximum 500KB text per document
- Maximum 50KB text per page
- Automatic truncation with warnings

## Limitations

- PDF text extraction works best with text-based PDFs (not scanned images)
- Field extraction uses regex patterns and may miss some variations
- LLM responses depend on model quality and speed
- Risk detection uses rule-based patterns
