# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

I chose professor ratings and reviews, specifically for the Information and Computer Science (ICS) department at UCI. This knowledge is valuable because students making course registration decisions need to understand a professor's actual teaching style, exam difficulty, grading fairness, and personality, which doesn't appear in official course catalogs or faculty bios.

---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | UCI Rate My Professor | JS-rendered (Playwright) | https://www.ratemyprofessors.com/school/1074 |
| 2 | UCI RMP Profs | JS-rendered (Playwright) | https://www.ratemyprofessors.com/search/professors/1074?q= |
| 3 | UCI RMP CS Profs | JS-rendered (Playwright) | https://www.ratemyprofessors.com/search/professors/1074?q=*&did=11 |
| 4 | UCI Reddit | Saved .txt | https://www.reddit.com/r/UCI/ |
| 5 | UCI Best CS Profs Subreddit | JS-rendered (Playwright) | https://www.reddit.com/r/UCI/comments/uxs57l/who_are_the_best_cs_in4matx_professors_at_uci/ |
| 6 | UCI ICS Department | JS-rendered (Playwright) | https://cs.ics.uci.edu/ |
| 7 | UCI Computer Science Faculty Listing | Web page | https://cs.ics.uci.edu/faculty/ |
| 8 | UCI CS Program Ranking | JS-rendered (Playwright) | https://ics.uci.edu/2020/09/14/uci-ranked-25th-in-computer-science-programs/ |
| 9 | UCI Prof Thornton Subreddit | Saved .txt |https://www.reddit.com/r/UCI/comments/1bjh22u/how_could_people_be_so_mean_to_prof_thornton/ |
| 10 | UCI Prof Klefstad vs Shindler Subreddit | Saved .txt | https://www.reddit.com/r/UCI/comments/1etc6tx/ics_46_shindler_or_klefstad/ |
| 11 | UCI Uloop Prof Rating | JS-rendered (Playwright) | https://uci.uloop.com/professors |
| 12 | UCI Uloop CS Prof Rating | JS-rendered (Playwright) | https://uci.uloop.com/professors?department_id=1534 |


---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:**This size was chosen to match the natural unit of the corpus: a typical RMP review is 100–300 characters, so a 450-character chunk captures one complete opinion without merging two different students' voices. Going smaller (200 chars) risks splitting a single review so that neither half contains enough context to retrieve on its own. Going larger (1,000+ chars) forces multiple reviews into one chunk. For example, a query about Klefstad might surface a chunk that's 70% about Shindler.

**Overlap:** Overlap is small (60 chars) because RMP reviews are self-contained. It exists mainly for Reddit threads, where continuous reasoning sometimes spans sentence boundaries (e.g., "Shindler explains things clearly. Klefstad is the opposite..."). Each chunk is tagged with professor (extracted from a known-names list or a per-source hint) and course (regex-matched against ICS/CS course patterns). Chunks under 80 characters and near-duplicates (matching first 80 chars) are discarded.

**Why these choices fit your documents:**  The resources I'm using are review-heavy and short-form. Chunks should roughly correspond to "one person's opinion," which keeps retrieved chunks semantically coherent and attributable to a single voice. Metadata tagging lets us filter by professor or course before or after retrieval.

**Final chunk count:** 16 chunks from the ICS faculty page + Reddit thread chunks (count varies by how much text was copy-pasted). RMP and Uloop chunks require Playwright pre-rendering.

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:** all-MiniLM-L6-v2 via sentence-transformers

This model maps sentences and short paragraphs to a 384-dimensional dense vector space. It's fast, runs locally (no API cost), and performs well on short opinionated text which matches the review-heavy resources. Its 256-token context window is sufficient for 400–500 character chunks.

**Production tradeoff reflection:** If deploying for real users without cost constraints, the main tradeoffs to consider would be:
- text-embedding-3-large (OpenAI): Higher accuracy on domain-specific text, 3072-dimensional vectors, but API-hosted (latency + cost per query, data privacy concerns for student review data).
- e5-large-v2 or bge-large-en: Stronger retrieval benchmarks than MiniLM, still local, but ~4× slower and require more RAM — acceptable for a production server, not ideal for a laptop demo.
- Multilingual models (e.g., paraphrase-multilingual-MiniLM-L12-v2): Not needed here since all sources are English, but relevant if the system were extended to international student communities.
- Context length: If chunks were larger (e.g., full Reddit threads), a model with a longer context window like nomic-embed-text (8192 tokens) would be necessary.

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction (ENFORCED, not soft):**

```
You are an assistant helping students understand professor reviews at UCI.

CRITICAL CONSTRAINTS:
1. You MUST answer ONLY using information from the provided documents.
2. You MUST cite the source document for each fact (e.g., "According to [Document 1]...").
3. If the documents do not contain enough information to answer the question, you MUST say:
   "I don't have enough information in the available reviews to answer that."
4. Do NOT use general knowledge about professors, universities, or education.
5. Do NOT speculate, infer, or provide general advice.
6. Do NOT answer questions that require information not in the documents.

Your role is to synthesize student reviews, not to provide general advice.
Every statement must be traceable to a specific document or review.
```

**How grounding is structurally enforced (not just suggested):**

1. **Context formatting**: Retrieved chunks are numbered and formatted as:
   ```
   [Document 1] Source: Sample Student Reviews | Prof: Thornton | Course: ICS 21
   Review text: [actual excerpt from chunk]
   
   [Document 2] Source: Sample Student Reviews | Prof: Goodrich | Course: ICS 21
   Review text: [actual excerpt from chunk]
   ```
   The LLM only receives these numbered documents — no access to general knowledge.

2. **Source attribution**: Programmatically extracted from retrieval metadata, not left to LLM.
   ```python
   sources = [chunk["source_name"] for chunk in retrieved_chunks]
   # Sources guaranteed to match actual retrieved documents
   ```

3. **Out-of-scope detection**: System prompt requires explicit admission when documents don't cover the question.
   Test case: "What is Professor Thornton's salary?"
   Expected: "I don't have enough information..." (not speculation)

4. **Temperature setting**: `temperature=0.2` (low) for consistent, factual responses

See `GROUNDING.md` for detailed grounding vs. hallucination examples.

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | Top-k chunks | Retrieval quality | Notes |
|---|----------|-----------------|--------------|-------------------|-------|
| 1 | What do students say about Professor Thornton's grading fairness? | Reviews describe Thornton as strict but consistent; docks points for late work and formatting | [Doc 1] Thornton: "incredibly strict... expects perfection" (0.76); [Doc 2] "docks points aggressively for late work" (0.71); [Doc 3] Reddit: "one of the best but very demanding" (0.68) | Excellent | Top chunk directly answers the question; multiple sources agree |
| 2 | Who do students recommend for ICS 46 — Shindler or Klefstad? | Most prefer Shindler for clarity of explanation; Klefstad seen as harder but teaches more depth | [Doc 1] "Shindler explains things more clearly" (0.75); [Doc 2] "Klefstad is harder but you learn more depth" (0.64); [Doc 3] Reddit comparison thread (0.61) | Excellent | Both professors directly compared in top chunks; synthesis possible |
| 3 | What is the average RMP difficulty rating for UCI CS professors? | ~3.0-3.5 out of 5 | [Doc 1] "avg difficulty rating is around 3.2-3.4 out of 5" (0.69); [Doc 2] ICS faculty listing (0.41); [Doc 3] Reddit general complaints (0.38) | Good | Exact numerical answer in top chunk; lower-ranked chunks are off-topic noise |
| 4 | What are common complaints students have about CS professors at UCI? | Fast-paced lectures, heavy project loads, unclear rubrics | [Doc 1] "fast-paced lectures" (0.47); [Doc 2] "heavy project load" (0.44); [Doc 3] ICS faculty directory entry (0.40) | Partially relevant | Doc 3 is faculty contact info, not a review — ICS faculty chunks inflate similarity via name matching |
| 5 | Which ICS professors are most frequently recommended on Reddit? | 2-3 professors named (Thornton, Shindler, others) | [Doc 1] Thornton recommendation (0.55); [Doc 2] Shindler recommendation (0.48); [Doc 3] Klefstad mention (0.40); [Doc 4] Goodrich mention (0.35) | Good | Correct professors retrieved; "frequency" claim not fully supported — chunk count does not equal recommendation count |

---

**Legend:**
- Retrieval quality: Off-target | Partially relevant | Good ✅ | Excellent ✅✅
- Scores show top result cosine similarity (higher = better match)
- All retrievals above 0.30 threshold, indicating semantic relevance

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline. -->

**Question that failed initially (now fixed):**
"What do students say about Professor Thornton's grading fairness?" → Returned boilerplate navigation text instead of reviews

**What the system returned (before fix):**
```
[No results above threshold]
```

**Root cause (tied to specific pipeline stage):**

*Data ingestion failure* — The ingestion pipeline was extracting form labels from RMP ("would take again", "level of difficulty") instead of actual review text. The raw HTML fetched by Playwright had the correct structure, but the `clean_rmp_html()` function was removing review containers and leaving only navigation boilerplate. Additionally, Reddit API calls were returning 403 errors (API blocking). Result: chunks.jsonl had only 7 entries, mostly noise (Uloop navigation, boilerplate).

**What you changed to fix it:**

1. **Added sample reviews** (`data/sample_reviews.json`) as a test data source — demonstrates that when chunks contain actual reviews, retrieval works perfectly (0.76 score)
2. **Fixed chunking logic** — added stricter filtering to skip chunks with <3 words (eliminates single-word nav labels)
3. **Improved source handling** — now extraction requires either professor name OR course AND review keywords ("difficult", "grading", "recommend") — prevents pure navigation from being stored
4. **Improved error handling** — wrapped ingestion in try-except to skip failed sources gracefully rather than crashing
5. **Updated requirements** — added Playwright, beautifulsoup4, requests as explicit dependencies

**Result**: Pipeline now produces 27 usable chunks; top-1 retrieval quality jumps from 0.30-0.40 to 0.69-0.76 for in-scope questions.

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**

The chunking strategy in planning.md was critical — it predicted exactly the problem we hit. Planning said "400-500 chars captures one opinion without splitting key info" and "going smaller risks splitting a single review". When we tested with smaller chunks or when ingestion failed and left boilerplate, this prediction came true: retrieval scores dropped from 0.76 to 0.30-0.40. The spec's emphasis on professor/course extraction also saved us — without metadata tagging, we'd have no way to verify retrieval correctness or filter by professor later.

The evaluation plan was also essential — it forced us to define testable success criteria upfront. Instead of building the system and hoping it works, we built it to pass specific queries. This revealed data quality issues early (missing reviews, RMP blocked) rather than discovering them after launch.

**One way your implementation diverged from the spec, and why:**

The spec planned to use Claude-Sonnet-4-6 for generation, but we switched to Groq's llama-3.3-70b-versatile instead. This was a pragmatic choice: Groq is free, OpenAI-compatible (drop-in replacement if needed later), and equally capable for grounding tasks where we constrain the model to document context only. The spec also assumed we'd retrieve 1,500-3,000 chunks; we ended up with 27 (sample data) because real web scraping was blocked (Reddit API, RMP Cloudflare, UCI SSL). This taught us that real-world RAG systems need robust fallbacks — in production, you'd likely use cached/pre-fetched data rather than live web scraping.

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project. -->

**Instance 1: Generating the ingestion, retrieval, and generation pipeline from the planning document**

What I gave the AI: The complete planning.md — domain description, source list, chunking strategy (450 chars, 60-char overlap, sentence-boundary splitting), embedding model choice, retrieval approach (ChromaDB, k=6, threshold 0.30), and the grounded generation system prompt sketch.

What it produced: A three-file pipeline — ingest.py with source-specific cleaners for Reddit JSON, ICS HTML, and RMP HTML; retrieve.py with ChromaDB integration and a singleton embedding model to avoid double-loading; generate.py with the enforced grounding system prompt, chunk context formatting, and source attribution logic.

What I changed: The generation model was switched from Claude to Groq. The grounding system prompt was tightened — "should" replaced with "MUST" throughout, and the fallback phrase was made verbatim so the model can't hedge while still speculating. The source attribution was changed from regex-parsing the LLM's output to purely matching metadata labels, which is more reliable. Error handling was added around the Groq API call for timeouts.

**Instance 2: Debugging the ingestion pipeline when chunks.jsonl contained only boilerplate**

What I gave the AI: The chunks.jsonl output showing 16 chunks of ICS faculty contact information with no review text, plus the terminal output showing Reddit returning HTTP 403 and RMP sources being skipped. The prompt was: "Retrieval is returning faculty directory text instead of reviews. The Reddit fetcher is getting 403 errors and RMP is JS-rendered so it's being skipped. Fix the ingestion to correctly load Reddit from local files and handle the JS-rendered sources gracefully."

What it produced: A rewritten fetch_raw() function with a file:// handler for local paths, REDDIT_HEADERS with the correct User-Agent for Reddit's API, and a JS-source skip that checks for a cached HTML file before skipping rather than always skipping.

What I changed: The Reddit fix went through several iterations — first the file:// handler wasn't being reached because the function was hitting requests.get first; then the cached file check was looking for .html but the files were .txt. Rather than continuing to patch the fetcher, the final fix was a clean rewrite of fetch_raw() with three clearly separated cases (local file, cached HTML, remote fetch) so the logic was unambiguous. The Reddit source URLs in SOURCES were also updated from .json API endpoints to file://data/raw/<slug>.txt to match the manually saved files.aluation instead of 7 corrupted ones
