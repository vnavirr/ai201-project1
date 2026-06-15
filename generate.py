"""
generate.py — UCI CS Professor RAG: Grounded answer generation

Pipeline:
  1. Retrieve top-k chunks from ChromaDB
  2. Format chunks as numbered context
  3. Send to Groq LLM with system prompt enforcing grounding
  4. Extract answer + source attribution
  5. Return structured result

Key engineering point: Grounding is ENFORCED via the system prompt,
not suggested. The model MUST cite sources or admit ignorance.
"""

import os
import re
from typing import TypedDict
from dotenv import load_dotenv
from groq import Groq

from retrieve import build_retriever, retrieve

load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

GROQ_MODEL = "llama-3.3-70b-versatile"


class QueryResult(TypedDict):
    """Structured result from a query."""
    answer: str
    sources: list[tuple[str, str]]  # (source_name, source_url)
    query: str


# System prompt that ENFORCES grounding, not just suggests it
SYSTEM_PROMPT = """You are an assistant helping students understand professor reviews at UCI.

CRITICAL CONSTRAINTS:
1. You MUST answer ONLY using information from the provided documents.
2. You MUST cite sources using ONLY these formats: [Reddit], [RateMyProfessors], [Uloop], [ICS Faculty], or [Sample].
3. Do NOT create citations like [Professor - Course - Source]. Use ONLY the source type.
4. Cite each claim only once—do NOT repeat the same source multiple times.
5. If the documents do not contain enough information to answer the question, you MUST say:
   "I don't have enough information in the available reviews to answer that."
6. Do NOT use general knowledge about professors, universities, or education.
7. Do NOT speculate, infer, or provide general advice.
8. Do NOT answer questions that require information not in the documents.

Your role is to synthesize student reviews, not to provide general advice.
EXAMPLE GOOD CITATION: "Students report that Professor Smith is rigorous [Reddit]"
EXAMPLE BAD CITATION: "According to [Professor Smith - CS 101 - RateMyProfessors]..."
Always use the simple source type format."""


def extract_source_type(display_name: str) -> str:
    """Extract clean source type from display name."""
    if "Reddit" in display_name:
        return "Reddit"
    elif "RMP" in display_name or "RateMyProfessors" in display_name:
        return "RateMyProfessors"
    elif "Uloop" in display_name:
        return "Uloop"
    elif "ICS" in display_name or "Faculty" in display_name:
        return "ICS Faculty"
    elif "Sample" in display_name:
        return "Sample"
    else:
        return display_name.split(":")[0].strip()


def format_context(retrieved_chunks: list[tuple[dict, float]]) -> tuple[str, list[tuple[str, str]]]:
    """
    Format retrieved chunks into context for the LLM with source names and URLs.

    Returns:
        (formatted_context_str, [(source_type, source_url), ...])
    """
    lines = []
    sources = {}  # source_type -> source_url (deduplicated by source_type)

    for i, (chunk, score) in enumerate(retrieved_chunks, 1):
        source_name = chunk["source_name"]
        source_type = extract_source_type(source_name)
        url = chunk["source_url"]
        prof = chunk["professor"] or "Unknown"
        course = chunk["course"] or "N/A"
        text = chunk["text"]

        lines.append(f"[Source: {source_type}] Prof: {prof} | Course: {course}")
        lines.append(f"Review text:\n{text}\n")

        if source_type not in sources:
            sources[source_type] = url

    context = "\n".join(lines)
    return context, sorted(list(sources.items()))


def ask(question: str, top_k: int = 6) -> QueryResult:
    """
    Answer a question by retrieving relevant chunks and grounding in LLM.

    Args:
        question: User's question
        top_k: Number of chunks to retrieve

    Returns:
        QueryResult with answer and sources (name, url tuples)
    """
    print(f"\n[query] {question}")

    # 1. Retrieve
    print(f"  [retrieve] Searching for relevant reviews...")
    collection = build_retriever()
    retrieved = retrieve(collection, question, top_k=top_k)

    if not retrieved:
        return QueryResult(
            answer="I don't have any relevant reviews to answer that question.",
            sources=[],
            query=question
        )

    # 2. Format context
    context, all_sources = format_context(retrieved)

    # 3. Call Groq with grounding constraint
    print(f"  [generate] Calling Groq (grounding enforced)...")

    user_message = f"""Based ONLY on the following student reviews, answer this question:

{context}

QUESTION: {question}

Remember: Answer ONLY from the above reviews. Cite your sources by name. If insufficient information, say so."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,  # Low temp for consistent, factual answers
            max_tokens=1024,
        )

        answer = response.choices[0].message.content

    except Exception as e:
        answer = f"[ERROR] Could not generate answer: {e}"
        print(f"  [ERROR] {e}")

    print(f"  [answer] Generated response")

    # 4. Extract actual sources cited in the answer, plus any sources with embedded references
    cited_sources = extract_cited_sources(answer, all_sources, retrieved)

    return QueryResult(
        answer=answer,
        sources=cited_sources,
        query=question
    )


def extract_cited_sources(answer: str, all_sources: list[tuple[str, str]], retrieved_chunks: list[tuple[dict, float]]) -> list[tuple[str, str]]:
    """
    Extract which sources are actually cited in the answer or present in chunks.

    Sources can be cited in the answer as [SourceType] or embedded in chunk text.
    """
    # Find citations in answer like [RateMyProfessors], [Reddit]
    cited_types = set(re.findall(r'\[([^\]]+)\]', answer))

    # Extract embedded source names from chunks (e.g., "RateMyProfessors" from "[Thornton - ICS 21 - RateMyProfessors]")
    embedded_sources = {}  # source_type -> url (inferred from embedded citations)
    for chunk, _ in retrieved_chunks:
        text = chunk.get("text", "")
        url = chunk.get("source_url", "")
        # Look for patterns like [... - Source] where Source is an actual source name
        embedded = re.findall(r'-\s+([\w\s]+(?:Professors)?)\]', text)
        for source in embedded:
            source = source.strip()
            if "RateMyProfessors" in source or "Rate My Professors" in source or source == "RMP":
                if "RateMyProfessors" not in embedded_sources:
                    embedded_sources["RateMyProfessors"] = url
            elif "Reddit" in source:
                if "Reddit" not in embedded_sources:
                    embedded_sources["Reddit"] = url
            elif "Uloop" in source:
                if "Uloop" not in embedded_sources:
                    embedded_sources["Uloop"] = url
            elif "Sample" in source:
                if "Sample" not in embedded_sources:
                    embedded_sources["Sample"] = url

    all_cited = cited_types | set(embedded_sources.keys())

    # Filter to matching sources from both metadata and embedded
    result = []
    for source_type, url in all_sources:
        if source_type in all_cited:
            result.append((source_type, url))

    # Add embedded sources that weren't in all_sources
    for source_type, url in embedded_sources.items():
        if source_type not in [s[0] for s in result]:
            result.append((source_type, url))

    return sorted(result)  # Sort for consistent display


if __name__ == "__main__":
    # Test grounding on a question the documents CAN answer
    print("\n" + "="*70)
    print("TEST 1: Question with sufficient context")
    print("="*70)
    result1 = ask("What do students say about Professor Thornton's grading fairness?")
    print(f"\nAnswer:\n{result1['answer']}")
    sources_str = ", ".join(f"[{name}]({url})" for name, url in result1['sources'])
    print(f"\nSources: {sources_str}")

    # Test grounding on a question the documents CANNOT answer
    print("\n" + "="*70)
    print("TEST 2: Question outside document scope (grounding test)")
    print("="*70)
    result2 = ask("What is the salary of Professor Thornton?")
    print(f"\nAnswer:\n{result2['answer']}")
    sources_str = ", ".join(f"[{name}]({url})" for name, url in result2['sources'])
    print(f"\nSources: {sources_str}")

    # Test grounding on a comparison question
    print("\n" + "="*70)
    print("TEST 3: Comparison question")
    print("="*70)
    result3 = ask("Who do students recommend for ICS 46 - Shindler or Klefstad?")
    print(f"\nAnswer:\n{result3['answer']}")
    sources_str = ", ".join(f"[{name}]({url})" for name, url in result3['sources'])
    print(f"\nSources: {sources_str}")
