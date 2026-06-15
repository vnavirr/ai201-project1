"""
ingest.py — UCI CS Professor RAG: Document Ingestion, Cleaning, and Chunking

Pipeline:
  1. Fetch raw HTML from each source URL
  2. Save raw HTML to data/raw/ (one file per source, never overwrite)
  3. Clean each document (source-specific logic)
  4. Chunk cleaned text (400–500 chars, 60-char overlap)
  5. Save chunks to data/chunks.jsonl (one JSON object per line)

Usage:
    pip install requests beautifulsoup4 praw
    python ingest.py

Output files:
    data/raw/<slug>.html      — raw HTML snapshots
    data/cleaned/<slug>.txt   — cleaned plain text
    data/chunks.jsonl         — one chunk dict per line
"""

import json
import os
import re
import time
import hashlib
from dataclasses import dataclass, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CHUNK_SIZE = 450        # target characters per chunk
CHUNK_OVERLAP = 60      # overlap between adjacent chunks
MIN_CHUNK_LEN = 80      # discard chunks shorter than this (noise/fragments)
REQUEST_DELAY = 2.0     # seconds between HTTP requests (be polite)

RAW_DIR = "data/raw"
CLEANED_DIR = "data/cleaned"
CHUNKS_FILE = "data/chunks.jsonl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

# Reddit blocks generic User-Agents; use a descriptive bot string + Accept header
REDDIT_HEADERS = {
    "User-Agent": "python:uci-prof-rag:v1.0 (educational project)",
    "Accept": "application/json",
}

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

SOURCES = [
    # --- Reddit threads (manually saved HTML — Reddit 403s on automated requests) ---
    {
        "slug": "reddit_best_cs_profs",
        "url": "file://data/raw/reddit_best_cs_profs.txt",
        "source_type": "reddit",
        "display_name": "Reddit: Best CS/INF4MATX Profs",
        "professor_hint": None,
    },
    {
        "slug": "reddit_thornton",
        "url": "file://data/raw/reddit_thornton.txt",
        "source_type": "reddit",
        "display_name": "Reddit: Prof Thornton Thread",
        "professor_hint": "Thornton",
    },
    {
        "slug": "reddit_klefstad_vs_shindler",
        "url": "file://data/raw/reddit_klefstad_vs_shindler.txt",
        "source_type": "reddit",
        "display_name": "Reddit: ICS 46 Klefstad vs Shindler",
        "professor_hint": None,
    },
    # --- UCI ICS faculty listing ---
    {
        "slug": "ics_faculty",
        "url": "https://cs.ics.uci.edu/faculty/",
        "source_type": "ics_faculty",
        "display_name": "UCI ICS Faculty Listing",
        "professor_hint": None,
    },
    # --- RMP individual professor pages (JS-rendered, fetched via Playwright) ---
    {
        "slug": "rmp_nadia_ahmed",
        "url": "https://www.ratemyprofessors.com/professor/2987203",
        "source_type": "rmp",
        "display_name": "RMP: Nadia Ahmed (UCI CS)",
        "professor_hint": "Ahmed",
    },
    {
        "slug": "rmp_alex_thornton",
        "url": "https://www.ratemyprofessors.com/professor/13200",
        "source_type": "rmp",
        "display_name": "RMP: Alex Thornton (UCI CS)",
        "professor_hint": "Thornton",
    },
    {
        "slug": "rmp_ray_klefstad",
        "url": "https://www.ratemyprofessors.com/professor/17490",
        "source_type": "rmp",
        "display_name": "RMP: Ray Klefstad (UCI CS)",
        "professor_hint": "Klefstad",
    },
    # --- RMP department search page (JS-rendered) ---
    {
        "slug": "rmp_uci_cs",
        "url": "https://www.ratemyprofessors.com/search/professors/1074?q=*&did=11",
        "source_type": "rmp",
        "display_name": "RMP: UCI CS Professors",
        "professor_hint": None,
    },
    # --- Uloop: also JS-rendered; included for reference ---
    {
        "slug": "uloop_cs",
        "url": "https://uci.uloop.com/professors?department_id=1534",
        "source_type": "uloop",
        "display_name": "Uloop: UCI CS Professors",
        "professor_hint": None,
    },
]

# Sources that require a JS renderer — skip gracefully and note for user
JS_ONLY_TYPES = {"rmp", "uloop"}

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    text: str
    source_type: str          # "reddit" | "ics_faculty" | "rmp" | "uloop"
    source_name: str          # human-readable source label
    source_url: str
    professor: Optional[str]  # best-effort professor name, or None
    course: Optional[str]     # e.g. "ICS 46", or None
    chunk_index: int          # position within the document
    chunk_id: str             # stable hash for deduplication

# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_raw(url: str, slug: str) -> Optional[str]:
    """Fetch URL and return raw text. Saves to data/raw/<slug>. Returns None on failure."""
    os.makedirs(RAW_DIR, exist_ok=True)
    raw_path = os.path.join(RAW_DIR, f"{slug}.html")

    # Use cached copy if available (re-run without re-scraping)
    if os.path.exists(raw_path):
        print(f"  [cache] {slug}")
        with open(raw_path, encoding="utf-8") as f:
            return f.read()

    print(f"  [fetch] {url}")
    try:
        _h = REDDIT_HEADERS if url.endswith(".json") else HEADERS
        resp = requests.get(url, headers=_h, timeout=15)
        resp.raise_for_status()
        raw = resp.text
    except requests.RequestException as e:
        print(f"  [ERROR] Could not fetch {url}: {e}")
        return None

    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw)

    time.sleep(REQUEST_DELAY)
    return raw

# ---------------------------------------------------------------------------
# Cleaning — source-specific
# ---------------------------------------------------------------------------

# Boilerplate phrases common across many pages
BOILERPLATE_FRAGMENTS = [
    "Sign in", "Log in", "Create account", "Cookie Policy", "Privacy Policy",
    "Terms of Service", "Rate My Professors", "Share", "Read more",
    "All Rights Reserved", "©", "Subscribe", "Newsletter",
    "JavaScript is disabled", "Enable JavaScript",
    "Advertisement", "Sponsored", "Skip to content",
    "Back to top", "Load more", "Show more comments",
]

def strip_boilerplate_lines(text: str) -> str:
    """Remove lines that are pure boilerplate."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(frag.lower() in stripped.lower() for frag in BOILERPLATE_FRAGMENTS):
            continue
        if len(stripped) < 15:   # likely a stray nav label or icon text
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned)


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace/newlines into single spaces or newlines."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_markdown_links(text: str) -> str:
    """Turn [label](url) into just label; remove bare URLs."""
    text = re.sub(r"\[([^\]]+)\]\(https?://[^\)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    return text


def clean_reddit_json(raw: str, professor_hint: Optional[str]) -> str:
    """
    Parse Reddit JSON API response.
    Extract: post title, post body, top-level comments, replies.
    Discard: deleted/removed content, mod comments, score < 1.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ""

    lines = []

    def extract_comments(listing):
        if not isinstance(listing, dict):
            return
        kind = listing.get("kind")
        d = listing.get("data", {})

        if kind == "Listing":
            for child in d.get("children", []):
                extract_comments(child)

        elif kind == "t3":  # Post
            title = d.get("title", "").strip()
            body = d.get("selftext", "").strip()
            if title:
                lines.append(f"[POST TITLE] {title}")
            if body and body not in ("[deleted]", "[removed]"):
                lines.append(remove_markdown_links(body))

        elif kind == "t1":  # Comment
            body = d.get("body", "").strip()
            score = d.get("score", 0)
            if body in ("[deleted]", "[removed]") or score < 1:
                return
            lines.append(remove_markdown_links(body))
            # Recurse into replies
            replies = d.get("replies")
            if isinstance(replies, dict):
                extract_comments(replies)

    # Reddit JSON returns a list of two listings: [post_listing, comments_listing]
    if isinstance(data, list):
        for listing in data:
            extract_comments(listing)
    else:
        extract_comments(data)

    text = "\n\n".join(lines)
    text = normalize_whitespace(text)
    return text


def clean_ics_faculty(raw: str) -> str:
    """
    Parse the ICS faculty listing page.
    Keep: faculty names, titles, research areas, email (for disambiguation).
    Discard: nav, footer, scripts, sidebar widgets.
    """
    soup = BeautifulSoup(raw, "html.parser")

    # Remove nav, footer, script, style, aside
    for tag in soup.find_all(["nav", "footer", "script", "style", "aside", "header"]):
        tag.decompose()

    # ICS faculty page uses .faculty-member or article/li blocks; grab all text
    # from main content area
    main = soup.find("main") or soup.find("div", id="content") or soup.find("body")
    if not main:
        return ""

    text = main.get_text(separator="\n")
    text = strip_boilerplate_lines(text)
    text = normalize_whitespace(text)
    return text


def clean_generic_html(raw: str) -> str:
    """Fallback cleaner for any HTML page."""
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup.find_all(["nav", "footer", "script", "style", "aside",
                               "header", "form", "iframe", "noscript"]):
        tag.decompose()
    # Remove elements likely to be ads or cookie banners
    for tag in soup.find_all(class_=re.compile(
        r"(cookie|banner|ad-|ads-|sidebar|social|share|related|comment-count)",
        re.I
    )):
        tag.decompose()

    body = soup.find("body") or soup
    text = body.get_text(separator="\n")
    text = strip_boilerplate_lines(text)
    text = normalize_whitespace(text)
    return text



def clean_reddit_html(raw: str) -> str:
    """
    Clean a manually saved Reddit thread HTML page.
    Keeps: post title, post body, comment text.
    Removes: nav, sidebars, buttons, vote counts, share links, ads.
    """
    soup = BeautifulSoup(raw, "html.parser")

    for tag in soup.find_all(["nav", "footer", "script", "style", "aside", "header", "iframe", "noscript"]):
        tag.decompose()

    # Reddit-specific noise: remove action bars, vote buttons, share/report links
    for tag in soup.find_all(class_=re.compile(
        r"(actionbar|awardings|promote|share|report|vote|ads|sidebar|community-info"
        r"|header|nav|subreddit-info|join|subscribe|search|login|signup|cookie"
        r"|flair|tag|award|trophy|banner|icon|community-details)",
        re.I
    )):
        tag.decompose()

    # Also remove by data-testid attributes Reddit uses
    for tag in soup.find_all(attrs={"data-testid": re.compile(
        r"(post-vote|comment-vote|share-button|report|award|join|subscribe)", re.I
    )}):
        tag.decompose()

    # Extract text — Reddit saved HTML keeps comment bodies in <p> and <div> tags
    body = soup.find("body") or soup
    text = body.get_text(separator="\n")
    text = strip_boilerplate_lines(text)
    text = remove_markdown_links(text)
    text = normalize_whitespace(text)

    # Drop lines that are clearly UI chrome: just numbers, single words, or icons
    lines = [l for l in text.split("\n") if len(l.split()) >= 4]
    return "\n".join(lines)

def clean_document(raw: str, source_type: str, professor_hint: Optional[str]) -> str:
    """Dispatch to the correct cleaner based on source type."""
    if source_type == "reddit":
        return clean_reddit_html(raw)
    elif source_type == "ics_faculty":
        return clean_ics_faculty(raw)
    else:
        # rmp and uloop are JS-rendered; if raw HTML somehow arrived, clean it generically
        return clean_generic_html(raw)

# ---------------------------------------------------------------------------
# Professor / course extraction
# ---------------------------------------------------------------------------

# Common UCI CS course patterns
COURSE_PATTERN = re.compile(
    r"\b(ICS|CS|COMPSCI|IN4MATX|I&C\s*SCI)\s*(\d{1,3}[A-Z]?)\b", re.IGNORECASE
)

# A rough list of known UCI CS professor last names for name extraction
KNOWN_PROFS = [
    "Ahmed", "Thornton", "Klefstad", "Shindler", "Pattis", "Dillencourt",
    "Frost", "Goodrich", "Irani", "Lathrop", "Lueker",
    "Petzold", "Eppstein", "Kay", "André", "Epstein",
    "Varanasi", "Dutt", "Gupta", "Sherwood",
]
PROF_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in KNOWN_PROFS) + r")\b",
    re.IGNORECASE,
)


def extract_professor(text: str, hint: Optional[str]) -> Optional[str]:
    if hint:
        return hint
    match = PROF_PATTERN.search(text)
    if match:
        return match.group(0).capitalize()
    return None


def extract_course(text: str) -> Optional[str]:
    match = COURSE_PATTERN.search(text)
    if match:
        dept = match.group(1).upper().replace(" ", "").replace("&", "")
        num = match.group(2).upper()
        return f"{dept} {num}"
    return None

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    source: dict,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    """
    Split text into overlapping character-based chunks.
    Each chunk inherits metadata from the source dict.
    Short fragments below MIN_CHUNK_LEN are discarded.
    Near-duplicate chunks (identical first 80 chars) are deduplicated.
    """
    if not text.strip():
        return []

    chunks = []
    start = 0
    index = 0
    seen_hashes = set()

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence boundary within the last 80 chars of the window
        if end < len(text):
            # Look for '. ', '! ', '? ', or '\n' near the end of the window
            boundary = max(
                text.rfind(". ", start, end),
                text.rfind("! ", start, end),
                text.rfind("? ", start, end),
                text.rfind("\n", start, end),
            )
            if boundary > start + chunk_size // 2:
                end = boundary + 1  # include the punctuation

        chunk_text_str = text[start:end].strip()

        if len(chunk_text_str) >= MIN_CHUNK_LEN:
            # Stable dedup hash
            chunk_hash = hashlib.md5(chunk_text_str.encode()).hexdigest()[:12]
            dedup_key = chunk_text_str[:80]

            if dedup_key not in seen_hashes:
                seen_hashes.add(dedup_key)
                professor = extract_professor(chunk_text_str, source.get("professor_hint"))
                course = extract_course(chunk_text_str)

                chunks.append(Chunk(
                    text=chunk_text_str,
                    source_type=source["source_type"],
                    source_name=source["display_name"],
                    source_url=source["url"],
                    professor=professor,
                    course=course,
                    chunk_index=index,
                    chunk_id=f"{source['slug']}_{index}_{chunk_hash}",
                ))
                index += 1

        # Advance with overlap
        start = end - overlap
        if start >= len(text):
            break

    return chunks

# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(CLEANED_DIR, exist_ok=True)

    all_chunks: list[Chunk] = []
    skipped_js = []

    for source in SOURCES:
        slug = source["slug"]
        stype = source["source_type"]
        print(f"\n{'='*60}")
        print(f"Processing: {source['display_name']}")

        # Skip JS-rendered sources gracefully
        if stype in JS_ONLY_TYPES:
            print(f"  [SKIP] {stype.upper()} pages require a JS renderer (Playwright/Selenium).")
            print(f"         To include this source, render the page and save HTML to:")
            print(f"         {RAW_DIR}/{slug}.html")
            print(f"         Then re-run this script — it will pick up the cached file.")
            skipped_js.append(source["display_name"])
            continue

        # 1. Fetch raw
        raw = fetch_raw(source["url"], slug)
        if raw is None:
            print(f"  [SKIP] Could not retrieve {slug}")
            continue

        # 2. Clean
        cleaned = clean_document(raw, stype, source.get("professor_hint"))
        if not cleaned.strip():
            print(f"  [WARN] Cleaning produced empty output for {slug}")
            continue

        cleaned_path = os.path.join(CLEANED_DIR, f"{slug}.txt")
        with open(cleaned_path, "w", encoding="utf-8") as f:
            f.write(cleaned)
        print(f"  [clean] {len(cleaned):,} chars → {cleaned_path}")

        # 3. Chunk
        chunks = chunk_text(cleaned, source)
        all_chunks.extend(chunks)
        print(f"  [chunk] {len(chunks)} chunks produced")

    # 4. Save chunks
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")

    print(f"\n{'='*60}")
    print(f"DONE: {len(all_chunks)} total chunks → {CHUNKS_FILE}")

    if skipped_js:
        print(f"\nSkipped (JS-rendered, need Playwright):")
        for name in skipped_js:
            print(f"  • {name}")
        print("\nTo scrape these, install Playwright:")
        print("  pip install playwright && playwright install chromium")
        print("  Then use: browser.new_page(); page.goto(url); page.content()")
        print("  Save the rendered HTML to data/raw/<slug>.html and re-run.")


if __name__ == "__main__":
    main()