# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

<!-- What domain did you choose? Why is this knowledge valuable and hard to find through official channels? -->
I chose professor ratings and reviews, specifically for the Information and Computer Science (ICS) department at UCI. This knowledge is valuable because students making course registration decisions need to understand a professor's actual teaching style, exam difficulty, grading fairness, and personality, which doesn't appear in official course catalogs or faculty bios.

---

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | UCI Rate My Professor | web page | https://www.ratemyprofessors.com/school/1074 |
| 2 | UCI RMP Profs | web page | https://www.ratemyprofessors.com/search/professors/1074?q= |
| 3 | UCI RMP CS Profs | web page | https://www.ratemyprofessors.com/search/professors/1074?q=*&did=11 |
| 4 | UCI Reddit | web page | https://www.reddit.com/r/UCI/ |
| 5 | UCI Best CS Profs Subreddit | web page | https://www.reddit.com/r/UCI/comments/uxs57l/who_are_the_best_cs_in4matx_professors_at_uci/ |
| 6 | UCI ICS Department | web page | https://cs.ics.uci.edu/ |
| 7 | UCI Computer Science Faculty Listing | web page | https://cs.ics.uci.edu/faculty/ |
| 8 | UCI CS Program Ranking | web page | https://ics.uci.edu/2020/09/14/uci-ranked-25th-in-computer-science-programs/ |
| 9 | UCI Prof Thornton Subreddit | web page |https://www.reddit.com/r/UCI/comments/1bjh22u/how_could_people_be_so_mean_to_prof_thornton/ |
| 10 | UCI Prof Klefstad vs Shindler Subreddit | web page | https://www.reddit.com/r/UCI/comments/1etc6tx/ics_46_shindler_or_klefstad/ |
| 11 | UCI Uloop Prof Rating | web page | https://uci.uloop.com/professors |
| 12 | UCI Uloop CS Prof Rating | web page | https://uci.uloop.com/professors?department_id=1534 |

---

## Chunking Strategy

<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size:** Most of the documents are short, opinion-based reviews with a typical RMP or Uloop review being 1–4 sentences, or around 100–300 characters. Reddit comments vary more with a short top-level comment being 50 words and a detailed reply comparing two professors going up to run 200+ words. A 400–500 character chunk captures one complete review or one coherent paragraph of a Reddit comment without slicing mid-thought. Going smaller (e.g., 200 characters) risks splitting a single review across two chunks so that neither contains enough context to be useful on its own. Going larger (e.g., 1,000+ characters) would force multiple reviews into one chunk, diluting retrieval precision. For example, a query about one professor could surface a chunk that's mostly about someone else if I go larger with the chunk size.

**Overlap:** Because RMP reviews are self-contained, overlap between adjacent RMP chunks is less critical — each chunk is likely a single review. However, Reddit threads often have continuous reasoning across sentences, so a small overlap ensures that the boundary between two chunks doesn't cut a comparison mid-sentence, making both chunks retrievable and coherent.

**Reasoning:** The resources I'm using are review-heavy and short-form. Chunks should roughly correspond to "one person's opinion," which keeps retrieved chunks semantically coherent and attributable to a single voice. Metadata tagging lets us filter by professor or course before or after retrieval.

---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model:** all-MiniLM-L6-v2 via sentence-transformers

This model maps sentences and short paragraphs to a 384-dimensional dense vector space. It's fast, runs locally (no API cost), and performs well on short opinionated text which matches the review-heavy resources. Its 256-token context window is sufficient for 400–500 character chunks.

**Top-k:** Retrieve k=6 chunks per query

Six chunks gives the LLM enough signal to synthesize an answer across multiple opinions (e.g., "several students agree that...") without flooding the context window. Too few (k=2–3) risks missing the most relevant review if the embedding similarity isn't perfect. Too many (k=15+) increases noise: tangentially related chunks about different professors or courses dilute the answer and can cause the LLM to hedge unhelpfully.

**Production tradeoff reflection:** If deploying for real users without cost constraints, the main tradeoffs to consider would be:
- text-embedding-3-large (OpenAI): Higher accuracy on domain-specific text, 3072-dimensional vectors, but API-hosted (latency + cost per query, data privacy concerns for student review data).
- e5-large-v2 or bge-large-en: Stronger retrieval benchmarks than MiniLM, still local, but ~4× slower and require more RAM — acceptable for a production server, not ideal for a laptop demo.
- Multilingual models (e.g., paraphrase-multilingual-MiniLM-L12-v2): Not needed here since all sources are English, but relevant if the system were extended to international student communities.
- Context length: If chunks were larger (e.g., full Reddit threads), a model with a longer context window like nomic-embed-text (8192 tokens) would be necessary.

---

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

| # | Question | Expected answer |
|---|----------|-----------------|
| 1 | What do students say about Professor Thornton's grading fairness? | Reviews should describe Thornton as harsh or strict in grading; some students find him unfair, others say he's consistent; Reddit thread r/UCI/1bjh22u should surface. | 
| 2 | Who do students recommend for ICS 46 — Shindler or Klefstad? | Retrieved chunks should reflect the Reddit comparison thread; most students prefer Shindler for clarity of explanation but note Klefstad is more lenient in grading. |
| 3 | What is the average RMP difficulty rating for UCI CS professors? | System should retrieve structured RMP data and synthesize a ballpark range; expected answer is roughly 3.0–3.5 out of 5. |
| 4 | What are common complaints students have about CS professors at UCI? | Top retrieved chunks should surface recurring themes: fast-paced lectures, heavy project loads, unclear rubrics — drawn from multiple RMP and Reddit sources. |
| 5 | Which ICS professors are most frequently recommended on Reddit? | Expected answer names 2–3 professors (e.g., Thornton for some courses, Shindler, others from the "best CS profs" thread) and links the sentiment to specific subreddit sources. |

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1. Review noise and subjectivity bias

Student reviews are inherently opinionated and not representative. A professor who had one bad quarter may have 10 negative reviews from that cohort skewing retrieval. Chunks from a single viral Reddit thread (e.g., the Thornton post) may dominate results for queries about that professor, drowning out more balanced perspectives from RMP. Mitigation: store source and date metadata and consider surfacing source diversity in the prompt to the LLM ("based on 4 RMP reviews and 2 Reddit comments...").

2. Professor name disambiguation and missing attribution

Many Reddit comments refer to professors by last name only, first name only, or nickname ("Prof T", "Klef"). Chunking may separate the name mention from the actual opinion, so the chunk containing "he explains things really well" has no recoverable professor identity. Metadata tagging during preprocessing helps, but name extraction from unstructured Reddit text is error-prone. Mitigation: use the page URL and thread title to infer the professor and inject that as a metadata field at the chunk level, even when the review body doesn't mention a name.

---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->


``` ascii
  ┌──────────────────────┐
  │  1. DOCUMENT         │   Sources: RMP, Reddit r/UCI, Uloop, ICS faculty page
  │     INGESTION        │   Tools:   requests + BeautifulSoup
  │                      │   Output:  raw text strings + metadata (source, prof, URL)
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │  2. CHUNKING         │   Size:    400–500 chars, 50–75 char overlap
  │                      │   Tools:   custom chunk_text() in Python
  │                      │   Output:  list of {text, source, professor, course} dicts
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │  3. EMBEDDING +      │   Model:   all-MiniLM-L6-v2 (sentence-transformers)
  │     VECTOR STORE     │   Store:   ChromaDB (persistent local collection)
  │                      │   Output:  384-dim vectors + metadata stored on disk
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │  4. RETRIEVAL        │   Query embedded with all-MiniLM-L6-v2
  │                      │   Top-k:   k=6, cosine similarity threshold ≥ 0.30
  │                      │   Output:  top-k chunks with source labels + scores
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │  5. GENERATION       │   Model:   claude-sonnet-4-6 (Anthropic API)
  │                      │   Prompt:  system grounding instruction + labeled chunks
  │                      │   Output:  answer with inline citations + Sources block
  └──────────────────────┘
```
---

## AI Tool Plan

<!-- For each part of the pipeline below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, which requirements)
     - What you expect it to produce
     - How you'll verify the output matches your spec

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Chunking Strategy section and ask it to implement chunk_text()
     with my specified chunk size and overlap" is a plan. -->

I'll give Claude my planning.md instruction and go through the pipeline step by step as to be able to check the correctness as we go alone. I will start with document ingestion and create clean_text(), specifying that it needs to be careful about thoroughly cleaning pages like RMP. Then for chunking, I'll ask it to implement chunk_text() with my specified chunk size and overlap.

**Milestone 3 — Ingestion and chunking:**

**Milestone 4 — Embedding and retrieval:**

**Milestone 5 — Generation and interface:**
