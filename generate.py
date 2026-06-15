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

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

GROQ_MODEL = "llama-3.3-70b-versatile"

# Valid source types — "sample" is intentionally excluded
VALID_SOURCE_TYPES = {"reddit", "rmp", "uloop", "ics_faculty"}


class QueryResult(TypedDict):
    answer: str
    sources: list[tuple[str, str]]   # (display_label, source_url)
    query: str


SYSTEM_PROMPT = """You are an assistant helping students understand professor reviews at UCI.

CRITICAL CONSTRAINTS:
1. Answer ONLY using information from the provided documents.
2. Cite each source using ONLY one of these exact labels: [Reddit], [RateMyProfessors], [Uloop], [ICS Faculty].
3. Do NOT use any other citation format (e.g. do not include professor names or course numbers in brackets).
4. Cite each source label at most once per sentence.
5. If the documents do not contain enough information, respond with exactly:
   "I don't have enough information in the available reviews to answer that."
6. Do NOT use general knowledge about professors, universities, or education.
7. Do NOT speculate or infer beyond what the documents say.

GOOD example: "Students report that Professor Smith is rigorous [Reddit]."
BAD example:  "According to [Thornton - ICS 21 - RateMyProfessors]..."
"""


def source_type_to_label(source_type: str) -> str:
    """Map internal source_type slug to the citation label used in the prompt."""
    return {
        "reddit":      "Reddit",
        "rmp":         "RateMyProfessors",
        "uloop":       "Uloop",
        "ics_faculty": "ICS Faculty",
    }.get(source_type, "")   # returns "" for unknown / sample — filtered below


def format_context(
    retrieved_chunks: list[tuple[dict, float]]
) -> tuple[str, list[tuple[str, str]]]:
    """
    Format retrieved chunks into context for the LLM.

    Skips any chunk whose source_type is not in VALID_SOURCE_TYPES
    (this is what drops sample chunks from both the context and the
    sources list that is shown to the user).

    Returns:
        context_str  — text block injected into the user message
        sources      — deduplicated [(label, url), ...] for valid sources only
    """
    lines = []
    seen_labels: dict[str, str] = {}   # label -> url, deduplicated

    for chunk, score in retrieved_chunks:
        stype = chunk.get("source_type", "")
        if stype not in VALID_SOURCE_TYPES:
            continue                        # ← drops "sample" chunks silently

        label = source_type_to_label(stype)
        url   = chunk["source_url"]
        prof  = chunk.get("professor") or "Unknown"
        course = chunk.get("course") or "N/A"

        lines.append(f"[Source: {label}] Prof: {prof} | Course: {course}")
        lines.append(f"{chunk['text']}\n")

        if label not in seen_labels:
            seen_labels[label] = url

    context = "\n".join(lines)
    sources  = sorted(seen_labels.items())   # alphabetical for stable display
    return context, sources


def extract_cited_sources(
    answer: str,
    all_sources: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """
    Return only the sources whose citation label actually appears in the answer.
    This prevents the sources panel from listing sources the LLM never mentioned.
    """
    cited_labels = set(re.findall(r'\[([^\]]+)\]', answer))
    return [(label, url) for label, url in all_sources if label in cited_labels]


def ask(question: str, top_k: int = 6) -> QueryResult:
    """
    Answer a question by retrieving relevant chunks and grounding the LLM.
    """
    print(f"\n[query] {question}")

    collection = build_retriever()
    retrieved  = retrieve(collection, question, top_k=top_k)

    if not retrieved:
        return QueryResult(
            answer="I don't have any relevant reviews to answer that question.",
            sources=[],
            query=question,
        )

    context, all_sources = format_context(retrieved)

    if not context.strip():
        # Every retrieved chunk was a sample chunk — nothing valid to ground on
        return QueryResult(
            answer="I don't have enough information in the available reviews to answer that.",
            sources=[],
            query=question,
        )

    user_message = (
        f"Based ONLY on the following student reviews, answer this question:\n\n"
        f"{context}\n"
        f"QUESTION: {question}\n\n"
        f"Remember: answer only from the reviews above and cite using "
        f"[Reddit], [RateMyProfessors], [Uloop], or [ICS Faculty]."
    )

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        answer = response.choices[0].message.content
    except Exception as e:
        answer = f"[ERROR] Could not generate answer: {e}"
        print(f"  [ERROR] {e}")

    cited_sources = extract_cited_sources(answer, all_sources)

    return QueryResult(answer=answer, sources=cited_sources, query=question)


if __name__ == "__main__":
    tests = [
        "What do students say about Professor Thornton's grading fairness?",
        "Who do students recommend for ICS 46 - Shindler or Klefstad?",
        "What is the salary of Professor Thornton?",   # should trigger "not enough info"
    ]

    for q in tests:
        print("\n" + "=" * 70)
        result = ask(q)
        print(f"\nAnswer:\n{result['answer']}")
        if result["sources"]:
            print("\nSources:")
            for label, url in result["sources"]:
                print(f"  • [{label}]({url})")
        else:
            print("\nSources: (none cited)")