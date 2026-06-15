# Grounding vs Hallucination Examples

## What is Grounding?

Grounding means your answer is traceable to specific documents you retrieved.
It's the opposite of hallucination, where the model sounds authoritative but draws from training knowledge.

---

## Example 1: Grading Fairness Question

### Query
"What do students say about Professor Thornton's grading fairness?"

### ✅ GROUNDED RESPONSE (from retrieve + generate)
```
According to student reviews in the database (Sample Student Reviews):

Professor Thornton is known for strict grading standards. One review states: 
"Professor Thornton is incredibly strict with grading. He expects perfection 
on every assignment and exam. Harsh grader but his feedback is detailed."

Another review notes: "Thornton's grading is fair but rigorous. He sticks to 
his rubric consistently. If you follow the requirements exactly, you'll get 
full marks. The issue is his rubric is extremely detailed and he doesn't give 
partial credit."

Sources: Sample Student Reviews (RateMyProfessors)
```

**Why this is grounded:**
- ✅ Every fact is quoted or paraphrased from retrieved chunks
- ✅ Source is explicitly cited
- ✅ No general knowledge about grading pedagogy
- ✅ Reflects actual student experiences in database

### ❌ HALLUCINATED RESPONSE (what we DON'T want)
```
Professor Thornton likely uses a rubric-based grading system common among 
computer science educators. He probably values both correctness and code 
quality, as most rigorous CS professors do. Students generally benefit from 
strict grading as it prepares them for industry standards. His exams probably 
emphasize algorithmic thinking and problem-solving skills.
```

**Why this is hallucinated:**
- ❌ Contains no quotes from actual reviews
- ❌ Uses words like "probably" and "likely" (model speculation)
- ❌ Draws from general knowledge about CS education
- ❌ Not traceable to any document in the database
- ❌ Sounds plausible but is false confidence

---

## Example 2: Out-of-Scope Question

### Query
"What is the salary of Professor Thornton?"

### ✅ GROUNDED RESPONSE (admits ignorance)
```
I don't have enough information in the available reviews to answer that. 
The database contains student reviews about teaching style, grading, and 
course difficulty, but does not include salary information.

Sources: (none - question is out of scope)
```

**Why this is grounded:**
- ✅ Explicitly admits the documents don't contain the information
- ✅ Explains what information IS available
- ✅ Doesn't speculate or guess

### ❌ HALLUCINATED RESPONSE (what we DON'T want)
```
Based on typical university compensation structures, Professor Thornton as 
a computer science faculty member at a top-tier UC campus likely earns 
between $120,000-$150,000 annually, with potential for additional research 
funding and summer salary supplements. This is competitive with industry 
salaries for comparable positions.
```

**Why this is hallucinated:**
- ❌ No source in the database supports these numbers
- ❌ Model is using general knowledge about university salaries
- ❌ No disclaimer that this is speculation
- ❌ Completely not traceable to our documents
- ❌ Dangerously misleading (sounds like real information)

---

## Example 3: Comparison Question

### Query
"Who do students recommend for ICS 46 - Shindler or Klefstad?"

### ✅ GROUNDED RESPONSE (synthesizes multiple sources)
```
According to student reviews in our database, the recommendation depends 
on your priorities:

SHINDLER is recommended by students who prioritize clarity and workload:
"Shindler explains things way better than Klefstad. His lectures are clear 
and organized. The workload is lighter too. Definitely recommend Shindler 
for ICS 46 if you want an easier time."

KLEFSTAD is recommended by students prioritizing depth of learning:
"Comparing Shindler and Klefstad: Klefstad is harder but teaches real 
systems programming. Shindler is easier but more shallow. If you want to 
actually understand data structures, take Klefstad. He's lenient with 
grading relative to difficulty."

In summary, Shindler = easier but shallower; Klefstad = harder but deeper.

Sources: Sample Student Reviews (Reddit)
```

**Why this is grounded:**
- ✅ Direct quotes from multiple reviews
- ✅ Presents both perspectives fairly
- ✅ Synthesizes rather than speculates
- ✅ All statements traceable to documents

### ❌ HALLUCINATED RESPONSE (what we DON'T want)
```
Both professors are well-qualified, but Klefstad is generally considered 
the superior instructor in terms of rigor. His systems-oriented approach 
aligns better with modern CS curriculum standards. Shindler may be easier, 
but "easier" isn't always better in CS education. Students who want to 
build a strong foundation in data structures should choose Klefstad.
```

**Why this is hallucinated:**
- ❌ No quotes from actual student reviews
- ❌ Model is pushing its own opinion ("superior", "better")
- ❌ Phrases like "generally considered" hide speculation
- ❌ Not traceable to any document
- ❌ Confident tone masks lack of grounding

---

## How Our System Prevents Hallucination

### Layer 1: System Prompt (Behavioral Constraint)
```
CRITICAL CONSTRAINTS:
1. You MUST answer ONLY using information from the provided documents.
2. You MUST cite the source document for each fact.
3. If documents don't contain enough info: "I don't have enough information..."
4. Do NOT use general knowledge. Do NOT speculate.
```

### Layer 2: Context Formatting (Structural Constraint)
```
[Document 1] Sample Student Reviews | Prof: Thornton
Review text: "Professor Thornton is incredibly strict with grading..."

[Document 2] Sample Student Reviews | Prof: Goodrich
Review text: "Goodrich is an excellent researcher..."
```

Only numbered documents are provided. Model has no access to general knowledge.

### Layer 3: Source Attribution (Programmatic Guarantee)
```python
result = {
    "answer": "...", 
    "sources": ["Sample Student Reviews"]  # Extracted by code, not LLM
}
```

Sources are extracted from metadata, not left to LLM to generate.

---

## Testing for Grounding: Checklist

When you test the system, ask yourself:

- [ ] Could this response have been written from general knowledge alone?
  - If YES = hallucination (grounding failure)
  - If NO = likely grounded

- [ ] Are there direct quotes or close paraphrases from documents?
  - If YES = good sign (probably grounded)
  - If NO = suspicious (probably hallucinated)

- [ ] Are sources explicitly cited?
  - If YES = essential for verification (grounding feature)
  - If NO = can't verify (potential hallucination)

- [ ] Does the response admit when information is unavailable?
  - If YES for out-of-scope questions = good grounding
  - If NO (speculates instead) = hallucination

- [ ] If you removed the retrieved documents, would the response still be plausible?
  - If YES = hallucination (not dependent on documents)
  - If NO = grounded (only makes sense with documents)

---

## Real-World Implications

**Without grounding**, your RAG system is just an LLM with a pretty UI:
- Students trust the "answer" and believe it's from real reviews
- System confidently presents hallucinations as facts
- Credibility destroyed when users discover false information
- Potential for harm (wrong advice about professors)

**With grounding**, your RAG system is trustworthy:
- Users can verify answers by reading source documents
- System admits when it lacks information
- Transparent about what data it has access to
- Credible tool for actual decision-making
