from typing import List, Dict, Tuple, Optional
import re
import os
import httpx
from app.database import get_document, list_documents
from app.pdf_processor import find_text_positions, get_page_from_position

class SimpleRAG:
    """RAG implementation with optional LLM support"""
    
    def __init__(self):
        # LLM configuration - supports multiple free options
        self.llm_enabled = os.getenv("LLM_ENABLED", "true").lower() == "true"
        self.llm_provider = os.getenv("LLM_PROVIDER", "ollama").lower()  # ollama, huggingface, groq, none
        
        # Ollama configuration (default - free, local)
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama2")  # or mistral, llama2:7b, etc.
        
        # Hugging Face (free tier)
        self.hf_api_key = os.getenv("HUGGINGFACE_API_KEY", "")
        self.hf_model = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.1")
        
        # Groq (free tier - very fast)
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        
        # OpenAI (if user has free credits)
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[Tuple[str, int, int]]:
        """Split text into chunks with character positions"""
        # Limit text size to prevent memory issues (max 500KB of text)
        MAX_TEXT_SIZE = 500000
        if len(text) > MAX_TEXT_SIZE:
            text = text[:MAX_TEXT_SIZE]
        
        chunks = []
        start = 0
        max_chunks = 1000  # Safety limit to prevent infinite loops
        chunk_count = 0
        
        while start < len(text) and chunk_count < max_chunks:
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk_text.rfind('.')
                last_newline = chunk_text.rfind('\n')
                break_point = max(last_period, last_newline)
                if break_point > chunk_size * 0.5:  # Only break if we're past halfway
                    end = start + break_point + 1
                    chunk_text = text[start:end]
            
            chunks.append((chunk_text, start, end))
            start = end - overlap
            chunk_count += 1
            
            # Safety check: if we're not making progress, break
            if start <= chunks[-1][1] if chunks else 0:
                break
        
        return chunks
    
    def search_relevant_chunks(self, query: str, text: str, top_k: int = 3) -> List[Dict]:
        """Find relevant text chunks for a query with improved matching"""
        if not text or len(text.strip()) == 0:
            return []
        
        # Limit text size to prevent memory issues
        MAX_TEXT_SIZE = 500000  # 500KB max
        if len(text) > MAX_TEXT_SIZE:
            # Use first and last parts of text (most relevant usually)
            text = text[:MAX_TEXT_SIZE//2] + "\n\n[... text truncated ...]\n\n" + text[-MAX_TEXT_SIZE//2:]
        
        query_lower = query.lower()
        query_terms = [t.strip() for t in query_lower.split() if len(t.strip()) > 2]
        
        # Add synonyms for common terms
        synonyms = {
            "confidentiality": ["confidential", "confidential information", "non-disclosure", "nda", "disclosure"],
            "confidential": ["confidentiality", "confidential information", "non-disclosure", "nda"],
            "party": ["parties", "company", "companies", "entity", "entities"],
            "date": ["effective date", "execution date", "dated"],
            "term": ["duration", "period", "length"],
            "liability": ["liability cap", "liability limit", "maximum liability"],
            "what": [],  # Remove common words
            "is": [],
            "are": [],
            "the": [],
        }
        
        # Expand query terms with synonyms
        expanded_terms = set(query_terms)
        for term in query_terms:
            if term in synonyms:
                expanded_terms.update(synonyms[term])
        
        # Remove common stop words from scoring
        stop_words = {"what", "is", "are", "the", "a", "an", "this", "that", "these", "those"}
        query_terms = [t for t in query_terms if t not in stop_words]
        
        chunks = self.chunk_text(text, chunk_size=1000, overlap=200)
        scored_chunks = []
        
        for chunk_text, start, end in chunks:
            if not chunk_text or len(chunk_text.strip()) < 50:  # Skip very short chunks
                continue
                
            chunk_lower = chunk_text.lower()
            score = 0
            
            # Score by exact term matches (higher weight)
            for term in query_terms:
                if term in chunk_lower:
                    score += chunk_lower.count(term) * 3
            
            # Score by synonym matches (lower weight)
            for term in expanded_terms:
                if term in chunk_lower and term not in query_terms:
                    score += chunk_lower.count(term) * 1.5
            
            # Bonus for phrase matches
            if len(query_terms) > 1:
                phrase = " ".join(query_terms)
                if phrase in chunk_lower:
                    score += 10
            
            # Even if no exact match, give a small score if any query word appears
            # This ensures we always return something if the document has content
            if score == 0 and query_terms:
                for term in query_terms:
                    if term in chunk_lower:
                        score = 0.5  # Minimal score to include it
            
            scored_chunks.append({
                "text": chunk_text,
                "start": start,
                "end": end,
                "score": score
            })
        
        # Sort by score and return top_k
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        
        # Always return at least some chunks if text exists, even with low scores
        if not scored_chunks and chunks:
            # Return first few chunks as fallback
            return [{
                "text": chunk[0],
                "start": chunk[1],
                "end": chunk[2],
                "score": 0.1
            } for chunk in chunks[:top_k]]
        
        return scored_chunks[:top_k]
    
    async def answer_question(self, question: str, document_ids: Optional[List[str]] = None) -> Dict:
        """Answer a question using RAG"""
        if document_ids is None:
            document_ids = await list_documents()
        
        if not document_ids:
            return {
                "answer": "No documents available to answer the question.",
                "citations": []
            }
        
        all_chunks = []
        
        # Search across all specified documents
        for doc_id in document_ids:
            doc = await get_document(doc_id)
            if not doc:
                continue
            
            text = doc["text_content"]
            
            # Limit text size before processing
            MAX_TEXT_SIZE = 500000  # 500KB max
            if len(text) > MAX_TEXT_SIZE:
                # Log warning but continue with truncated text
                print(f"Warning: Document text is {len(text)} chars, truncating to {MAX_TEXT_SIZE}")
                text = text[:MAX_TEXT_SIZE]
            
            chunks = self.search_relevant_chunks(question, text, top_k=2)
            
            for chunk in chunks:
                chunk["document_id"] = doc_id
                chunk["page"] = get_page_from_position(text, chunk["start"])
                all_chunks.append(chunk)
        
        # If no chunks found, try a more lenient search or use the whole document
        if not all_chunks:
            # Try searching with a more lenient approach - use entire document
            for doc_id in document_ids:
                doc = await get_document(doc_id)
                if not doc:
                    continue
                
                text = doc["text_content"]
                if text and len(text) > 100:
                    # Limit text size
                    MAX_FALLBACK_SIZE = 10000
                    text_to_use = text[:MAX_FALLBACK_SIZE] if len(text) > MAX_FALLBACK_SIZE else text
                    
                    # Use the whole document as context if search failed
                    all_chunks = [{
                        "text": text_to_use,
                        "start": 0,
                        "end": len(text_to_use),
                        "score": 0.1,
                        "document_id": doc_id,
                        "page": 1
                    }]
                    break
        
        if not all_chunks:
            return {
                "answer": "I couldn't find relevant information to answer this question in the provided documents. Please ensure documents have been uploaded and contain text content.",
                "citations": []
            }
        
        # Sort all chunks by score
        all_chunks.sort(key=lambda x: x["score"], reverse=True)
        top_chunks = all_chunks[:3]
        
        # Generate answer from top chunks
        # Limit total context to prevent slow LLM processing
        context_chunks = [chunk["text"] for chunk in top_chunks]
        context = "\n\n".join(context_chunks)
        
        # Limit context size for faster LLM processing
        MAX_CONTEXT_FOR_LLM = 2000
        if len(context) > MAX_CONTEXT_FOR_LLM:
            # Take first chunk and truncate
            context = context_chunks[0][:MAX_CONTEXT_FOR_LLM] if context_chunks else context[:MAX_CONTEXT_FOR_LLM]
        
        # Use LLM if enabled, otherwise use simple extraction
        if self.llm_enabled and self.llm_provider != "none":
            try:
                answer = await self._generate_answer_with_llm(question, context)
            except Exception as e:
                # If LLM fails (timeout, etc.), fall back to simple extraction
                error_msg = str(e)
                if "timeout" in error_msg.lower():
                    print(f"LLM timeout - using simple extraction. Error: {error_msg}")
                else:
                    print(f"LLM error - using simple extraction. Error: {error_msg}")
                answer = self._generate_answer(question, context)
        else:
            answer = self._generate_answer(question, context)
        
        # Build citations
        citations = []
        for chunk in top_chunks:
            citations.append({
                "document_id": chunk["document_id"],
                "page": chunk["page"],
                "char_range": [chunk["start"], chunk["end"]],
                "text_snippet": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"]
            })
        
        return {
            "answer": answer,
            "citations": citations
        }
    
    def _generate_answer(self, question: str, context: str) -> str:
        """Generate an answer from context using simple extraction"""
        
        question_lower = question.lower()
        
        # Handle "what is" questions
        if "what is" in question_lower or "what does" in question_lower:
            # Extract the key term
            key_term = None
            for term in ["confidentiality", "confidential", "indemnity", "liability", "termination", "auto-renewal"]:
                if term in question_lower:
                    key_term = term
                    break
            
            if key_term:
                # Find sentences containing the key term
                sentences = context.split('.')
                relevant = [s.strip() for s in sentences if key_term.lower() in s.lower()]
                if relevant:
                    # Return the most relevant sentence(s)
                    answer = ". ".join(relevant[:2]) + "."
                    return answer[:500]  # Limit length
        
        # Try to find direct answers in context
        if "when" in question_lower or "date" in question_lower:
            # Look for dates
            date_pattern = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}"
            dates = re.findall(date_pattern, context)
            if dates:
                return f"Based on the document, the relevant date is: {dates[0]}"
        
        if "who" in question_lower or "party" in question_lower:
            # Look for parties
            party_pattern = r"([A-Z][A-Za-z\s&,\.]+?)(?:\s+and\s+|\s+,\s+)([A-Z][A-Za-z\s&,\.]+?)"
            parties = re.findall(party_pattern, context)
            if parties:
                return f"The parties mentioned are: {', '.join(parties[0])}"
        
        if "how much" in question_lower or "amount" in question_lower or "price" in question_lower:
            # Look for amounts
            amount_pattern = r"\$[\d,]+(?:\.\d{2})?|[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP)"
            amounts = re.findall(amount_pattern, context)
            if amounts:
                return f"Based on the document, the amount is: {amounts[0]}"
        
        # Default: return relevant context snippet
        sentences = context.split('.')
        query_terms = [t for t in question_lower.split() if len(t) > 2]
        relevant_sentences = [
            s.strip() for s in sentences 
            if any(term in s.lower() for term in query_terms)
        ]
        
        if relevant_sentences:
            answer = ". ".join(relevant_sentences[:3]) + "."
            return answer[:500]
        
        # Fallback: return first part of context
        return "Based on the document: " + context[:400] + "..."
    
    async def _generate_answer_with_llm(self, question: str, context: str) -> str:
        """Generate answer using LLM (supports multiple free providers)"""
        try:
            if self.llm_provider == "ollama":
                return await self._generate_with_ollama(question, context)
            elif self.llm_provider == "huggingface" and self.hf_api_key:
                return await self._generate_with_huggingface(question, context)
            elif self.llm_provider == "groq" and self.groq_api_key:
                return await self._generate_with_groq(question, context)
            elif self.llm_provider == "openai" and self.openai_api_key:
                return await self._generate_with_openai(question, context)
            else:
                # Fallback to simple extraction
                return self._generate_answer(question, context)
        except Exception as e:
            # If LLM fails, fallback to simple extraction
            error_msg = str(e) if e else "Unknown error"
            print(f"LLM error: {error_msg}, falling back to simple extraction")
            import traceback
            traceback.print_exc()  # Print full traceback for debugging
            return self._generate_answer(question, context)
    
    async def _generate_with_ollama(self, question: str, context: str) -> str:
        """Generate answer using Ollama (free, local)"""
        # Reduce context size to speed up processing
        context_snippet = context[:1500]  # Reduced from 3000 to 1500 for faster processing
        
        prompt = f"""Based on this contract text, answer the question:

{context_snippet}

Question: {question}

Answer:"""

        # Increase timeout to 120 seconds for slower models
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                try:
                    health_check = await client.get(f"{self.ollama_url}/api/tags", timeout=5.0)
                    if health_check.status_code != 200:
                        raise Exception(f"Ollama health check failed with status {health_check.status_code}")
                except httpx.ConnectError:
                    raise Exception(f"Cannot connect to Ollama at {self.ollama_url}. Is Ollama running?")
                
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 300,  # Reduced from 500 for faster response
                            "num_ctx": 2048,  # Limit context window
                        }
                    },
                    timeout=120.0  # Increased timeout
                )
                
                if response.status_code != 200:
                    error_text = response.text[:200] if hasattr(response, 'text') else "Unknown error"
                    raise Exception(f"Ollama API returned status {response.status_code}: {error_text}")
                
                result = response.json()
                
                if "error" in result:
                    error_msg = result.get("error", "Unknown error")
                    if "model" in error_msg.lower() and "not found" in error_msg.lower():
                        raise Exception(f"Model '{self.ollama_model}' not found. Run: ollama pull {self.ollama_model}")
                    raise Exception(f"Ollama error: {error_msg}")
                
                answer = result.get("response", "").strip()
                if not answer:
                    raise Exception("Ollama returned empty response")
                
                return answer
                
            except httpx.ConnectError as e:
                raise Exception(f"Cannot connect to Ollama at {self.ollama_url}. Make sure Ollama is running. Error: {str(e)}")
            except httpx.TimeoutException:
                raise Exception(f"Ollama request timed out. Try a smaller model or use Groq API for faster responses.")
            except Exception as e:
                raise Exception(f"Ollama generation failed: {str(e)}")
    
    async def _generate_with_huggingface(self, question: str, context: str) -> str:
        """Generate answer using Hugging Face Inference API (free tier)"""
        prompt = f"""Based on this contract text, answer the question:

{context[:2000]}

Question: {question}

Answer:"""

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://api-inference.huggingface.co/models/{self.hf_model}",
                headers={"Authorization": f"Bearer {self.hf_api_key}"},
                json={"inputs": prompt}
            )
            response.raise_for_status()
            result = response.json()
            
            # Handle different response formats
            if isinstance(result, list) and len(result) > 0:
                return result[0].get("generated_text", "").replace(prompt, "").strip()
            return str(result)
    
    async def _generate_with_groq(self, question: str, context: str) -> str:
        """Generate answer using Groq API (free tier, very fast)"""
        prompt = f"""You are a contract analysis assistant. Based on the following contract text, answer the question.

Contract Text:
{context[:3000]}

Question: {question}

Answer:"""

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama2-70b-4096",
                    "messages": [
                        {"role": "system", "content": "You are a contract analysis assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500
                }
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
    
    async def _generate_with_openai(self, question: str, context: str) -> str:
        """Generate answer using OpenAI (if user has free credits)"""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.openai_api_key)
            
            prompt = f"""You are a contract analysis assistant. Based on the following contract text, answer the question accurately.

Contract Text:
{context[:3000]}

Question: {question}

Answer the question based only on the contract text above."""

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a contract analysis assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
        except ImportError:
            raise Exception("OpenAI package not installed. Run: pip install openai")

rag = SimpleRAG()


