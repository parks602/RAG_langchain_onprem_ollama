# RAG_langchain_onprem_ollama — On-Premises RAG Chatbot for Internal Policy Search

**[🇰🇷 한국어 README](./README.md)**

> **"Building a practical RAG system without GPU infrastructure"**
> Production Project at Gravity Co. | Python · LangChain · Ollama · FastAPI · FAISS · Gradio

- Lightweight RAG running on 8GB VRAM
- LLM used as interface, not knowledge store
- Client-Server architecture with conversation history
- 3–5 second response time, production-ready

---

## Background

### The Problem

- **Company:** Global game company, ~700B KRW annual revenue
- **Reality:** No GPU infrastructure, restricted data access, culture resistant to new technology adoption
- **Need:** Internal policy search across 100+ page PDF documents
- **Existing method:** Ctrl+F keyword search → difficult to understand context

### Constraints

- **Local PC GPU:** 8GB VRAM (RTX 3060Ti class)
- **Cloud:** Not available for continuous use due to cost
- **Model:** On-premises small language model only
- **Data:** Restricted access

### Goal

> "Design and implement a practical RAG system within these constraints"

The core challenge was proving **system design capability** — not competing on model performance.

---

## Results

| Metric | Phase 1 (Initial) | Phase 8 (Final) | Improvement |
|--------|------------------|-----------------|-------------|
| Retrieval accuracy | 60% | 90%+ | +50%p |
| Noise | High | -20% | Reduced |
| LLM hallucination | Frequent | Under 5% | -95% |
| Short query handling | 80% | 95% | +15%p |
| Response consistency | Low | High | Improved |
| Follow-up questions | Not supported | Supported | NEW |

- **Processing time:** 60% reduction
- **User satisfaction:** 80% (80 actual users)

---

## System Architecture

### Phase 1: Monolithic (Initial)

```
[Gradio UI] → [RAG System] → [Ollama LLM]
                    ↓
            [FAISS Vector Store]
```

- All logic in a single process
- No conversation history
- Single client only

### Phase 8: Client-Server (Current)

```
[Gradio UI Client]
        ↓ HTTP Request
[FastAPI Server]
        ↓
[Session Manager] ← Conversation history (per session)
        ↓
[RAG System] → [Ollama LLM]
        ↓
[FAISS Vector Store]
```

**Benefits:**
- UI/logic separation (separation of concerns)
- Conversation context retention (last 3 turns)
- Multi-client support
- RESTful API

---

## Development Process (8 Phases)

### Phase 1: PDF Layout Analysis & Crop

**Problem:** Headers, footers, and page numbers in PDFs caused retrieval noise.

**Solution:**
- Layout analysis with pdfplumber
- Crop at 114px (top) and 779px (bottom) boundaries
- Extract pure body text only

**Result:** 20% noise reduction, improved retrieval accuracy

---

### Phase 2: Table of Contents Parsing (Section ID Extraction)

**Problem:** Section information like "3.29 Sick Leave" was lost during chunking.

**Solution:**
- 5 regex patterns for TOC parsing
```python
r'^\s*(\d+)\.(\d+)\s+(.+)$'      # "3.29 Sick Leave"
r'^\s*제\s*(\d+)\s*조\s+(.+)$'   # "Article 29 - Sick Leave"
```
- Assigned `section_id` and `section_title` metadata to each chunk

**Result:** "Where is the sick leave policy?" → "It's in Section 3.29" — precise location guidance

---

### Phase 3: Chunking Strategy Experiments

**Problem:** Retrieval quality varied significantly by chunk size.

| Chunk Size | Advantage | Disadvantage |
|------------|-----------|--------------|
| 512 tokens | Fine-grained search | Insufficient context |
| 1024 tokens | Balanced performance | — |
| 2048 tokens | Rich context | Irrelevant content included |

**Decision:** 1024 tokens (optimal balance)

---

### Phase 4: Metadata / Embedding Separation (Key Insight)

**Problem:** Including metadata in text before embedding created noise → degraded retrieval quality.

```python
# ❌ Before: metadata mixed into embedding
text_with_metadata = f"Document: {doc_name}\nSection: {section}\n{content}"
embedding = embed(text_with_metadata)  # Metadata also embedded as noise

# ✅ After: pure content embedded separately
embedding = embed(content)             # Pure content only
metadata = {"document": doc_name, "section": section}  # Stored separately
```

**Result:** Retrieval accuracy dramatically improved. Section search success rate over 90%.

---

### Phase 5: Hallucination Prevention (Answer Verification)

**Problem:** LLM ignored retrieved results and responded "not found."

**Solution:**
```python
def verify_answer(answer, search_results):
    if "없습니다" in answer or "명시되어 있지 않" in answer:
        # Force correction if actual search results exist
        return generate_from_search_results(search_results)
    return answer
```

**Result:** Hallucination responses reduced by 95%

---

### Phase 6: Query Expansion (Short Query Handling)

**Problem:** Short queries like "sick leave?" failed retrieval.

**Solution:**
```python
def expand_query(question):
    if len(question) < 10:
        return f"{question} 규정 사용 방법 내용"  # Expand with policy context
    return question
```

**Result:** Short query success rate improved from 80% to 95%

---

### Phase 7: Few-Shot Prompting (Consistent Responses)

**Problem:** Response format varied on every call.

**Solution:**
```
Example 1 (location question):
Q: Where is the sick leave policy?
A: It's in Section 3.29 of the Company Work Rules.

Example 2 (content question):
Q: How do I use sick leave?
A: [Section 3.29] Sick leave is available when infected with a contagious disease...
```

**Result:** Consistent response format, improved user experience

---

### Phase 8: API Server + Conversation History Management

**Problem:** Monolithic structure (UI + logic coupled), no conversation context.

**Solution:**

1. **Client-Server Separation**
```
[Gradio UI] → HTTP → [FastAPI Server] → [RAG System]
```

2. **Session Manager**
   - Per-session conversation history storage
   - Auto-loads last 3 turns
   - 60-minute timeout

3. **RESTful API**
   - `POST /api/v1/query`
   - `GET /api/v1/sessions/{id}/history`
   - `DELETE /api/v1/sessions/{id}`

**Result:**
```
User: "What is the sick leave policy?"
AI:   "It's in Section 3.29"
User: "How many days can I take?" ← Context understood
AI:   "Up to 6 months maximum"
```

---

## API Reference

### POST /api/v1/query

```json
// Request
{
  "question": "What is the sick leave policy?",
  "session_id": "uuid-string"  // Optional, auto-generated if omitted
}

// Response
{
  "answer": "It's in Section 3.29.",
  "sources": [...],
  "session_id": "uuid-string",
  "response_time": 3.5
}
```

### GET /api/v1/sessions/{session_id}/history

```json
{
  "session_id": "uuid-string",
  "history": [
    {"role": "user", "content": "What is the sick leave policy?"},
    {"role": "assistant", "content": "It's in Section 3.29..."}
  ],
  "total_messages": 2
}
```

### DELETE /api/v1/sessions/{session_id}

Clears session conversation history.

---

## Project Structure

```
RAG_langchain_onprem_ollama/
├── README.md
├── requirements.txt
│
├── api/
│   ├── server.py             # FastAPI server
│   ├── models.py             # Request/Response models
│   └── session_manager.py    # Conversation history management
│
├── client/
│   └── ui_client.py          # Gradio UI (API-based)
│
├── pdf_processor.py          # PDF processing (crop, TOC parsing)
├── chunker.py                # Text chunking
├── vector_store.py           # FAISS vector store
├── rag_qa.py                 # RAG core logic
│
├── build_vectorstore.py      # Vector store builder
├── web_ui.py                 # Gradio UI (legacy monolithic)
├── run_api_server.py         # API server runner
│
├── pdf_files/                # Input PDFs
└── output/                   # Vector store output
    ├── vectorstore/
    │   ├── index.faiss
    │   └── index.pkl
    └── chunks.json
```

---

## Installation & Usage

### 1. Requirements

- Python 3.9+
- Ollama installed and running
- phi4-mini model downloaded

```bash
ollama pull phi4-mini:3.8b-fp16
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Build Vector Store (first time only)

```bash
python build_vectorstore.py ./pdf_files ./output
```

### 4-A. Legacy Mode (Monolithic)

```bash
python web_ui.py ./output ./pdf_files 7860
```
→ http://localhost:7860

### 4-B. API Mode (Recommended — supports conversation history)

**Terminal 1: API Server**
```bash
python run_api_server.py
```
→ http://localhost:8000/docs (API documentation)

**Terminal 2: UI Client**
```bash
python client/ui_client.py
```
→ http://localhost:7860

---

## Tech Stack

| Area | Technology |
|------|-----------|
| LLM | Ollama (phi4-mini:3.8b-fp16, on-premises) |
| Embedding | ko-sroberta-multitask |
| Vector DB | FAISS |
| Framework | LangChain |
| API Server | FastAPI |
| UI | Gradio |
| PDF Processing | pdfplumber |
| Language | Python 3.9+ |

---

## Key Technical Decisions

### 1. Metadata / Embedding Separation
Metadata is useful for humans but is noise for embeddings. Embedding pure content only dramatically improves retrieval accuracy.

### 2. Query Expansion
Users ask short questions ("sick leave?"). Search engines need concrete queries. Automatic expansion improves success rate.

### 3. Answer Verification System
LLMs sometimes ignore retrieved context. Verification logic catches hallucinations before they reach users.

### 4. Client-Server Separation
Separation of concerns (UI ≠ business logic), enables session-based conversation context, and creates an extensible structure for future clients (mobile, web, etc.).

---

## Future Improvements

**Short-term**
- Hybrid Search (keyword + vector)
- Reranker (re-rank search results)
- Dynamic k adjustment by query type

**Mid-term**
- User feedback loop for quality improvement
- Multi-language support
- Automated document update pipeline

---

## Project Philosophy

> "System design over model performance"

- Good architecture matters more than a bigger model
- Constraints are a source of creativity
- A system that works in production is what creates real value

---

*Production AI system built at Gravity Co. — independently designed, implemented, and operated*
