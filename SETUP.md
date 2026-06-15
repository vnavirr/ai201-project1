# Setup Instructions for UCI CS Professor RAG

## 1. Get a Free Groq API Key

1. Go to https://console.groq.com
2. Sign up (free, no credit card required)
3. Copy your API key
4. Edit `.env` and replace `your_key_here` with your actual key:

```
GROQ_API_KEY=gsk_your_actual_key_here
```

5. Save the file (it's already in `.gitignore` — your key won't be committed)

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## 3. Run the Tests

### Test end-to-end generation (requires API key):
```bash
python generate.py
```

### Launch the web interface:
```bash
python app.py
```

Then open `http://localhost:7860` in your browser.

## How the System Works

1. **Ingestion** (`ingest.py`): Fetches and chunks professor reviews
2. **Retrieval** (`retrieve.py`): Uses embeddings to find relevant chunks
3. **Generation** (`generate.py`): Calls Groq LLM with grounding prompt
4. **Interface** (`app.py`): Gradio web UI for asking questions

## Key Engineering: Grounding

The system enforces grounding through:
- **System prompt** that forbids general knowledge
- **Context formatting** that numbers and cites sources
- **Explicit instructions** to admit ignorance if docs don't cover the question

If the LLM tries to answer from training knowledge (not from documents), it's a grounding failure.
