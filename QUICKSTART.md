## 🚀 Quick Start — UCI CS Professor RAG

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Groq API Key (Free)
- Go to https://console.groq.com
- Sign up (no credit card)
- Copy your API key
- Edit `.env`: `GROQ_API_KEY=gsk_your_key_here`

### 3. Test Grounding (No API Key Required)
```bash
python demo.py
```
Shows how the system retrieves relevant chunks for each query.

### 4. Run Full System (Requires API Key)
```bash
python generate.py
```
Tests end-to-end: retrieval → grounded generation → response with sources.

### 5. Launch Web Interface
```bash
python app.py
```
Open browser to: `http://localhost:7860`

---

## 📁 Project Files

```
.
├── ingest.py              # Document ingestion & chunking
├── retrieve.py            # Semantic search via ChromaDB
├── generate.py            # Grounded LLM generation (Groq)
├── app.py                 # Gradio web interface
├── demo.py                # Grounding demo (no API needed)
├── test_retrieval.py      # Retrieval test script
│
├── README.md              # Main documentation (this file)
├── SYSTEM.md              # System architecture & overview
├── GROUNDING.md           # Grounding vs hallucination examples
├── SETUP.md               # Detailed setup instructions
├── planning.md            # Original project specification
│
├── data/
│   ├── chunks.jsonl       # Embedded chunks (27 total)
│   ├── sample_reviews.json# Sample review data
│   ├── raw/               # Raw HTML/JSON from sources
│   ├── cleaned/           # Cleaned text (preprocessed)
│   └── chroma_db/         # Vector DB (persistent storage)
│
├── .env                   # API keys (not committed)
└── requirements.txt       # Python dependencies
```

---

## ✅ What's Complete

- ✅ **Ingestion**: Fetches, cleans, chunks documents (27 chunks)
- ✅ **Retrieval**: Semantic search with cosine similarity (scores 0.30-0.76)
- ✅ **Generation**: Groq LLM with HARD grounding constraints
- ✅ **Interface**: Gradio web UI at localhost:7860
- ✅ **Evaluation**: Tested on 5 questions from planning.md
- ✅ **Grounding**: System prompt enforces document-only answers
- ✅ **Source Attribution**: Programmatic (from metadata, not LLM)
- ✅ **Out-of-Scope**: System admits ignorance for salary/unknown questions
- ✅ **Documentation**: SYSTEM.md, GROUNDING.md, SETUP.md

---

## 📊 Test Results

| Query | Top Score | Status | Example |
|-------|-----------|--------|---------|
| Thornton's grading? | 0.76 | ✅ Grounded | "incredibly strict... expects perfection" |
| Shindler vs Klefstad? | 0.75 | ✅ Grounded | "Shindler explains better... Klefstad harder" |
| Avg difficulty? | 0.69 | ✅ Grounded | "3.2-3.4 out of 5" |
| Common complaints? | 0.47 | ✅ Grounded | "fast-paced, heavy projects" |
| Salary of Thornton? | 0.43 | ✅ Admits ignorance | "I don't have enough info" |

---

## 🔐 Grounding Verification

The system is grounded if:
- ✅ Answers are quoted or closely paraphrased from retrieved chunks
- ✅ Sources explicitly cited (e.g., "According to Document 1")
- ✅ No speculative language ("probably", "likely", "generally")
- ✅ Out-of-scope questions get "I don't have enough information"
- ✅ Response couldn't be written from general knowledge alone

See `GROUNDING.md` for detailed examples.

---

## 🛠️ Troubleshooting

**"ModuleNotFoundError: No module named..."**
```bash
pip install -r requirements.txt
```

**"GROQ_API_KEY not set"**
1. Get free key from https://console.groq.com
2. Add to `.env`: `GROQ_API_KEY=gsk_...`

**"ChromaDB collection not found"**
```bash
python -c "from retrieve import build_retriever; build_retriever(force_rebuild=True)"
```

**"Gradio port 7860 already in use"**
```bash
python app.py --server_port 7861
```

---

## 📚 Learn More

- `SYSTEM.md` — Full architecture, data pipeline, engineering decisions
- `GROUNDING.md` — Grounding examples, hallucination vs truth
- `planning.md` — Original spec, chunking strategy, evaluation plan
- `SETUP.md` — Detailed setup and troubleshooting

---

## 🎯 Next Steps

1. **Try it**: `python demo.py` (no setup needed)
2. **Deploy it**: Get API key, `python app.py`, share URL
3. **Extend it**: Add more review sources, support multi-turn queries
4. **Production**: Use real Reddit/RMP data, add user feedback loop

