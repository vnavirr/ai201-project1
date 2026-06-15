"""
demo.py — Demonstrate the grounding pipeline (without requiring Groq API key)

Shows:
1. Retrieval step
2. Formatted context
3. What the LLM would receive (system prompt + context + question)
4. Example grounded response
"""

from retrieve import build_retriever, retrieve


def demo_retrieval_and_formatting():
    """Show the retrieval + formatting pipeline."""
    print("\n" + "="*70)
    print("UCI CS PROFESSOR RAG — GROUNDING DEMONSTRATION")
    print("="*70)

    queries = [
        "What do students say about Professor Thornton's grading fairness?",
        "Who do students recommend for ICS 46 - Shindler or Klefstad?",
        "What is the average RMP difficulty rating for UCI CS professors?",
        "What is the salary of Professor Thornton?",  # Out of scope
    ]

    collection = build_retriever()

    for query in queries:
        print(f"\n{'='*70}")
        print(f"QUERY: {query}")
        print(f"{'='*70}")

        # Retrieve
        retrieved = retrieve(collection, query, top_k=6)

        if not retrieved:
            print("[RETRIEVAL] No chunks above threshold")
            print("[GROUNDING] System would respond: 'I don't have enough information...'")
            continue

        print(f"\n[RETRIEVAL] Found {len(retrieved)} relevant chunks:\n")

        # Show what the LLM receives
        print("[CONTEXT FORMATTED FOR LLM]:")
        print("-" * 70)

        for i, (chunk, score) in enumerate(retrieved, 1):
            source = chunk["source_name"]
            prof = chunk["professor"] or "Unknown"
            course = chunk["course"] or "N/A"
            text = chunk["text"][:150] + "..." if len(chunk["text"]) > 150 else chunk["text"]

            print(f"[Document {i}] {source} | Prof: {prof} | Course: {course} (score: {score:.2f})")
            print(f"  {text}\n")

        print("-" * 70)
        print("\n[SYSTEM PROMPT (enforces grounding)]:")
        print("-" * 70)
        print("""You are an assistant helping students understand professor reviews at UCI.

CRITICAL CONSTRAINTS:
1. You MUST answer ONLY using information from the provided documents.
2. You MUST cite the source document for each fact.
3. If documents don't contain enough info: "I don't have enough information..."
4. Do NOT use general knowledge. Do NOT speculate.
5. Every statement must be traceable to a specific document.
""")

        print("-" * 70)
        print(f"\n[USER QUESTION]: {query}\n")

        print("[EXPECTED BEHAVIOR]:")
        if "salary" in query.lower():
            print("  > System should admit it doesn't have salary info (out of scope)")
        else:
            print("  > System should answer using the retrieved chunks above")
            print("  > Each fact should cite a document (e.g., 'According to [Document 1]...')")
            print("  > No general knowledge, only what's in the chunks")


if __name__ == "__main__":
    demo_retrieval_and_formatting()

    print(f"\n{'='*70}")
    print("DEMONSTRATION COMPLETE")
    print("="*70)
    print("""
To run the full system with LLM generation:

1. Add your Groq API key to .env:
   GROQ_API_KEY=gsk_your_key_here

2. Run generate.py to test end-to-end:
   python generate.py

3. Launch the web interface:
   python app.py
   (then open http://localhost:7860)

See SETUP.md for detailed instructions.
""")
