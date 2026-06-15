"""
retrieve.py — UCI CS Professor RAG: Embedding and Retrieval

Pipeline:
  1. Load chunks from data/chunks.jsonl
  2. Embed with all-MiniLM-L6-v2 (sentence-transformers)
  3. Store in ChromaDB with metadata (professor, course, source, URL)
  4. Retrieve top-k=6 chunks via semantic similarity

Usage:
    from retrieve import build_retriever, retrieve

    retriever = build_retriever()
    results = retrieve(retriever, "Is Klefstad hard?")
    for chunk, score in results:
        print(f"{chunk['professor']} — {score:.2f}")
        print(f"  {chunk['text'][:100]}...")
"""

import json
import os
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

# Config
CHUNKS_FILE = "data/chunks.jsonl"
CHROMA_DB = "data/chroma_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TOP_K = 6
SIMILARITY_THRESHOLD = 0.30


def load_chunks(path: str = CHUNKS_FILE) -> list[dict]:
    """Load chunks from JSONL file."""
    chunks = []
    if not os.path.exists(path):
        print(f"[ERROR] Chunks file not found: {path}")
        return chunks

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))

    print(f"[load] {len(chunks)} chunks loaded from {path}")
    return chunks


def build_retriever(force_rebuild: bool = False) -> chromadb.Collection:
    """
    Build or load ChromaDB collection with embeddings.

    If collection already exists and force_rebuild=False, loads it.
    Otherwise, loads chunks from JSONL and embeds them.
    """
    # Initialize ChromaDB client (persistent storage in data/chroma_db)
    os.makedirs(CHROMA_DB, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DB)

    # Check if collection exists
    existing_collections = [c.name for c in client.list_collections()]
    if "uci_profs" in existing_collections and not force_rebuild:
        print("[load] ChromaDB collection 'uci_profs' already exists, loading...")
        collection = client.get_collection(name="uci_profs")
        return collection

    # Load chunks
    chunks = load_chunks()
    if not chunks:
        print("[ERROR] No chunks to embed")
        return None

    # Initialize embedding model
    print(f"[model] Loading {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    # Delete old collection if rebuilding
    if "uci_profs" in existing_collections:
        client.delete_collection(name="uci_profs")

    # Create collection
    collection = client.create_collection(
        name="uci_profs",
        metadata={"hnsw:space": "cosine"}
    )

    # Embed and store chunks
    print(f"[embed] Embedding {len(chunks)} chunks...")
    for i, chunk in enumerate(chunks):
        if (i + 1) % 5 == 0:
            print(f"  {i + 1}/{len(chunks)}")

        # Embed text
        embedding = model.encode(chunk["text"], convert_to_numpy=True)

        # Store in ChromaDB with metadata
        collection.add(
            ids=[chunk["chunk_id"]],
            embeddings=[embedding],
            documents=[chunk["text"]],
            metadatas=[{
                "professor": chunk.get("professor") or "Unknown",
                "course": chunk.get("course") or "Unknown",
                "source_type": chunk["source_type"],
                "source_name": chunk["source_name"],
                "source_url": chunk["source_url"],
                "chunk_index": chunk["chunk_index"],
            }]
        )

    print(f"[store] {len(chunks)} chunks stored in ChromaDB")
    return collection


def retrieve(
    collection: chromadb.Collection,
    query: str,
    top_k: int = TOP_K,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[tuple[dict, float]]:
    """
    Retrieve top-k chunks most similar to the query.

    Args:
        collection: ChromaDB collection
        query: User query string
        top_k: Number of results to return
        threshold: Minimum cosine similarity score (0.0–1.0)

    Returns:
        List of (chunk_metadata, similarity_score) tuples, sorted by score descending
    """
    # Embed query with same model
    model = SentenceTransformer(EMBEDDING_MODEL)
    query_embedding = model.encode(query, convert_to_numpy=True)

    # Query ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    # Format results: convert distances to similarity scores (cosine distance → similarity)
    # ChromaDB returns distances, we convert to similarity: similarity = 1 - distance
    retrieved = []
    if results["metadatas"] and results["metadatas"][0]:
        for i, metadata in enumerate(results["metadatas"][0]):
            distance = results["distances"][0][i]
            similarity = 1 - distance  # Convert distance to similarity

            if similarity >= threshold:
                chunk = {
                    "text": results["documents"][0][i],
                    "professor": metadata["professor"],
                    "course": metadata["course"],
                    "source_type": metadata["source_type"],
                    "source_name": metadata["source_name"],
                    "source_url": metadata["source_url"],
                }
                retrieved.append((chunk, similarity))

    return retrieved


if __name__ == "__main__":
    # Example usage
    collection = build_retriever()

    if collection:
        print("\n" + "="*60)
        print("RETRIEVAL TEST")
        print("="*60)

        queries = [
            "Is Professor Klefstad hard?",
            "Which professor is best for ICS 46?",
            "What's the difficulty of data structures?",
        ]

        for query in queries:
            print(f"\n[Q] {query}")
            results = retrieve(collection, query)

            if not results:
                print("  [No results above threshold]")
            else:
                for i, (chunk, score) in enumerate(results, 1):
                    print(f"\n  [{i}] {chunk['professor']} — {chunk['course']} ({score:.2f})")
                    print(f"      Source: {chunk['source_name']}")
                    print(f"      {chunk['text'][:120]}...")
