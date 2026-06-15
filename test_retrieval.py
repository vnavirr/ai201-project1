"""Test retrieval with the 5 evaluation plan queries."""

from retrieve import build_retriever, retrieve

# The 5 evaluation plan queries
QUERIES = [
    "What do students say about Professor Thornton's grading fairness?",
    "Who do students recommend for ICS 46 — Shindler or Klefstad?",
    "What is the average RMP difficulty rating for UCI CS professors?",
    "What are common complaints students have about CS professors at UCI?",
    "Which ICS professors are most frequently recommended on Reddit?",
]

def test_queries():
    collection = build_retriever()

    if not collection:
        print("[ERROR] Failed to load collection")
        return

    print("\n" + "="*70)
    print("EVALUATION PLAN RETRIEVAL TEST")
    print("="*70)

    for i, query in enumerate(QUERIES[:3], 1):  # Test first 3 queries
        print(f"\n[Q{i}] {query}")
        print("-" * 70)

        results = retrieve(collection, query, top_k=6)

        if not results:
            print("  [No results above threshold (0.30)]")
        else:
            for j, (chunk, score) in enumerate(results, 1):
                distance = 1 - score  # Convert similarity back to distance
                print(f"\n  [{j}] Score: {score:.2f} (distance: {distance:.2f})")
                print(f"      Prof: {chunk['professor']} | Course: {chunk['course']}")
                print(f"      Source: {chunk['source_name']}")
                print(f"      Text: {chunk['text'][:150]}...")

if __name__ == "__main__":
    test_queries()
