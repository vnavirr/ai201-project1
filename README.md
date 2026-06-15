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

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:** Most of the documents are short, opinion-based reviews with a typical RMP or Uloop review being 1–4 sentences, or around 100–300 characters. Reddit comments vary more with a short top-level comment being 50 words and a detailed reply comparing two professors going up to run 200+ words. A 400–500 character chunk captures one complete review or one coherent paragraph of a Reddit comment without slicing mid-thought. Going smaller (e.g., 200 characters) risks splitting a single review across two chunks so that neither contains enough context to be useful on its own. Going larger (e.g., 1,000+ characters) would force multiple reviews into one chunk, diluting retrieval precision. For example, a query about one professor could surface a chunk that's mostly about someone else if I go larger with the chunk size.

**Overlap:** Because RMP reviews are self-contained, overlap between adjacent RMP chunks is less critical — each chunk is likely a single review. However, Reddit threads often have continuous reasoning across sentences, so a small overlap ensures that the boundary between two chunks doesn't cut a comparison mid-sentence, making both chunks retrievable and coherent.

**Why these choices fit your documents:**  The resources I'm using are review-heavy and short-form. Chunks should roughly correspond to "one person's opinion," which keeps retrieved chunks semantically coherent and attributable to a single voice. Metadata tagging lets us filter by professor or course before or after retrieval.

**Final chunk count:** Approximately 1,500–3,000 chunks depending on how many individual RMP reviews are scraped and how many Reddit comments are collected. 

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

**System prompt grounding instruction:**

**How source attribution is surfaced in the response:**

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 |  | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:**

**What the system returned:**

**Root cause (tied to a specific pipeline stage):**

**What you would change to fix it:**

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**

**One way your implementation diverged from the spec, and why:**

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:*
- *What it produced:*
- *What I changed or overrode:*

**Instance 2**

- *What I gave the AI:*
- *What it produced:*
- *What I changed or overrode:*
