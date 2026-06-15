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
import random
from dataclasses import dataclass, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CHUNK_SIZE = 450        # target characters per chunk
CHUNK_OVERLAP = 60      # overlap between adjacent chunks
MIN_CHUNK_LEN = 150     # discard chunks shorter than this (noise/fragments)
REQUEST_DELAY = 2.0     # seconds between HTTP requests (be polite)

RAW_DIR = "data/raw"
CLEANED_DIR = "data/cleaned"
CHUNKS_FILE = "data/chunks.jsonl"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

SOURCES = [
    # --- Sample review data (for testing when real sources fail) ---
    {
        "slug": "sample_reviews",
        "url": "file://data/sample_reviews.json",
        "source_type": "sample",
        "display_name": "Sample Student Reviews",
        "professor_hint": None,
    },
    # --- Reddit threads (use JSON API; no scraping needed) ---
    {
        "slug": "reddit_best_cs_profs",
        "url": "https://www.reddit.com/r/UCI/comments/uxs57l/who_are_the_best_cs_in4matx_professors_at_uci/.json",
        "source_type": "reddit",
        "display_name": "Reddit: Best CS/INF4MATX Profs",
        "professor_hint": None,
    },
    {
        "slug": "reddit_thornton",
        "url": "https://www.reddit.com/r/UCI/comments/1bjh22u/how_could_people_be_so_mean_to_prof_thornton/.json",
        "source_type": "reddit",
        "display_name": "Reddit: Prof Thornton Thread",
        "professor_hint": "Thornton",
    },
    {
        "slug": "reddit_klefstad_vs_shindler",
        "url": "https://www.reddit.com/r/UCI/comments/1etc6tx/ics_46_shindler_or_klefstad/.json",
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
    # --- RMP pages: blocked by Cloudflare when headless; included for reference.
    #     If you have a Playwright/Selenium setup, swap fetch_html() below.
    #     For now these are skipped with a clear warning. ---
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

def fetch_raw_playwright(url: str, slug: str) -> Optional[str]:
    """Fetch URL using Playwright (handles JS rendering). Saves to data/raw/<slug>.html."""
    os.makedirs(RAW_DIR, exist_ok=True)
    raw_path = os.path.join(RAW_DIR, f"{slug}.html")

    if os.path.exists(raw_path):
        print(f"  [cache] {slug}")
        with open(raw_path, encoding="utf-8") as f:
            return f.read()

    print(f"  [fetch-playwright] {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)  # Extra time for JS to settle
            html = page.content()
            browser.close()
    except Exception as e:
        print(f"  [ERROR] Could not fetch {url}: {e}")
        return None

    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(html)

    time.sleep(REQUEST_DELAY)
    return html


def fetch_raw(url: str, slug: str) -> Optional[str]:
    """Fetch URL and return raw text. Saves to data/raw/<slug>. Returns None on failure."""
    os.makedirs(RAW_DIR, exist_ok=True)
    raw_path = os.path.join(RAW_DIR, f"{slug}.html")

    # Use cached copy if available (re-run without re-scraping)
    if os.path.exists(raw_path):
        print(f"  [cache] {slug}")
        with open(raw_path, encoding="utf-8") as f:
            return f.read()

    # Handle local file:// URLs
    if url.startswith("file://"):
        local_path = url.replace("file://", "")
        print(f"  [load] {local_path}")
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                raw = f.read()
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(raw)
            return raw
        except Exception as e:
            print(f"  [ERROR] Could not read {local_path}: {e}")
            return None

    print(f"  [fetch] {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
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
    "Accept cookies", "We use cookies", "Cookie settings",
    "Search by", "Department", "Filter", "Sort by",
    "More info", "Learn more", "Click here", "Get started",
    "Follow us", "Connect with", "Social media", "Share on",
    "Copyright", "Contact us", "About us", "Help",
    "Mobile app", "Download", "Available on", "Get it on",
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


def clean_rmp_html(raw: str) -> str:
    """Clean RMP professor pages: extract actual review content."""
    soup = BeautifulSoup(raw, "html.parser")

    # Remove nav, footer, ads, sidebars
    for tag in soup.find_all(["nav", "footer", "script", "style", "header", "aside"]):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(
        r"(navbar|sidebar|ad|cookie|banner|modal|search-bar|filter)",
        re.I
    )):
        tag.decompose()

    # Try to extract review containers
    main = soup.find("main") or soup.find("div", class_=re.compile("content|results", re.I)) or soup.find("body")
    if main:
        # Remove very common RMP boilerplate
        for tag in main.find_all(string=re.compile(r"(Sign in|Rate|Professors|Search|Department|Filter|Sort)", re.I)):
            tag.extract()

    text = main.get_text(separator="\n") if main else ""
    text = strip_boilerplate_lines(text)
    text = normalize_whitespace(text)

    # Remove lines that are just numbers, stars, or single words
    lines = [l for l in text.split("\n") if len(l.split()) >= 3]
    text = "\n".join(lines)

    return text


def clean_uloop_html(raw: str) -> str:
    """Clean Uloop professor pages: extract review/rating content."""
    soup = BeautifulSoup(raw, "html.parser")

    # Remove nav, footer, ads, sidebars
    for tag in soup.find_all(["nav", "footer", "script", "style", "header", "aside", "form"]):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(
        r"(navbar|sidebar|ad|cookie|banner|modal|filter|search)",
        re.I
    )):
        tag.decompose()

    # Extract main content area
    main = soup.find("main") or soup.find("div", class_=re.compile("content|results|professor", re.I)) or soup.find("body")
    if main:
        text = main.get_text(separator="\n")
    else:
        text = soup.get_text(separator="\n")

    text = strip_boilerplate_lines(text)
    text = normalize_whitespace(text)

    # Remove lines that are just numbers, single words, or navigation
    lines = [l for l in text.split("\n") if len(l.split()) >= 3]
    text = "\n".join(lines)

    return text


def clean_sample_reviews(raw: str) -> str:
    """Load sample reviews from JSON and format as text."""
    try:
        data = json.loads(raw)
        reviews = data.get("sample_reviews", [])
        lines = []
        for rev in reviews:
            prof = rev.get("professor", "Unknown")
            course = rev.get("course", "Unknown")
            source = rev.get("source", "Sample")
            text = rev.get("review", "")
            lines.append(f"[{prof} - {course} - {source}]\n{text}\n")
        return "\n".join(lines)
    except json.JSONDecodeError:
        return ""


def clean_document(raw: str, source_type: str, professor_hint: Optional[str]) -> str:
    """Dispatch to the correct cleaner based on source type."""
    if source_type == "sample":
        return clean_sample_reviews(raw)
    elif source_type == "reddit":
        return clean_reddit_json(raw, professor_hint)
    elif source_type == "ics_faculty":
        return clean_ics_faculty(raw)
    elif source_type == "rmp":
        return clean_rmp_html(raw)
    elif source_type == "uloop":
        return clean_uloop_html(raw)
    else:
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
    "Thornton", "Klefstad", "Shindler", "Pattis", "Dillencourt",
    "Frost", "Goodrich", "Irani", "Lathrop", "Lueker",
    "Petzold", "Eppstein", "Kay", "André", "Epstein",
    "Varanasi", "Dutt", "Gupta", "Sherwood", "Varanasi",
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
    Chunks without meaningful content (no prof/course mention) may be skipped.
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
            boundary = max(
                text.rfind(". ", start, end),
                text.rfind("! ", start, end),
                text.rfind("? ", start, end),
                text.rfind("\n", start, end),
            )
            if boundary > start + chunk_size // 2:
                end = boundary + 1

        chunk_text_str = text[start:end].strip()

        if len(chunk_text_str) >= MIN_CHUNK_LEN:
            chunk_hash = hashlib.md5(chunk_text_str.encode()).hexdigest()[:12]
            dedup_key = chunk_text_str[:80]

            if dedup_key not in seen_hashes:
                seen_hashes.add(dedup_key)
                professor = extract_professor(chunk_text_str, source.get("professor_hint"))
                course = extract_course(chunk_text_str)

                # For RMP/Uloop, require at least professor or course mention
                if source["source_type"] in ("rmp", "uloop"):
                    if not professor and not course:
                        # Try harder: check if chunk mentions teaching/difficulty/ratings
                        if not re.search(r"(teach|difficult|hard|easy|rating|review|skill|good|bad|recommend)", chunk_text_str, re.I):
                            # Skip this chunk—it's likely boilerplate
                            start = end - overlap
                            if start >= len(text):
                                break
                            continue

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

    for source in SOURCES:
        slug = source["slug"]
        stype = source["source_type"]
        print(f"\n{'='*60}")
        print(f"Processing: {source['display_name']}")

        try:
            # 1. Fetch raw (use Playwright for JS-rendered sources)
            if stype in JS_ONLY_TYPES:
                raw = fetch_raw_playwright(source["url"], slug)
            else:
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
            print(f"  [clean] {len(cleaned):,} chars saved to {cleaned_path}")

            # 3. Chunk
            chunks = chunk_text(cleaned, source)
            all_chunks.extend(chunks)
            print(f"  [chunk] {len(chunks)} chunks produced")

        except Exception as e:
            print(f"  [ERROR] Exception processing {slug}: {e}")
            continue

    # 4. Save chunks
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")

    print(f"\n{'='*60}")
    print(f"DONE: {len(all_chunks)} total chunks saved to {CHUNKS_FILE}")

    # Sample and print 5 random chunks for testing
    if all_chunks:
        sample_size = min(5, len(all_chunks))
        random_chunks = random.sample(all_chunks, sample_size)
        print(f"\n{'='*60}")
        print(f"SAMPLE: {sample_size} random chunks")
        print(f"{'='*60}")
        for i, chunk in enumerate(random_chunks, 1):
            print(f"\n[{i}] {chunk.source_name} | Prof: {chunk.professor} | Course: {chunk.course}")
            print(f"    Chunk ID: {chunk.chunk_id}")
            print(f"    Text: {chunk.text[:200]}...")


if __name__ == "__main__":
    main()