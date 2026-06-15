"""
ingest.py — UCI CS Professor RAG: Document Ingestion, Cleaning, and Chunking

Pipeline:
  1. Load each source (local file:// or remote URL)
  2. Save remote fetches to data/raw/ as cache
  3. Clean each document (source-specific logic)
  4. Chunk cleaned text (~450 chars, 60-char overlap)
  5. Save chunks to data/chunks.jsonl (one JSON object per line)

Usage:
    pip install requests beautifulsoup4
    python ingest.py
"""

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CHUNK_SIZE    = 450
CHUNK_OVERLAP = 60
MIN_CHUNK_LEN = 80
REQUEST_DELAY = 2.0

RAW_DIR     = "data/raw"
CLEANED_DIR = "data/cleaned"
CHUNKS_FILE = "data/chunks.jsonl"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

SOURCES = [
    # Reddit threads — saved manually as .txt (Reddit blocks automated requests)
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
    # UCI ICS faculty listing (plain HTTP, no JS needed)
    {
        "slug": "ics_faculty",
        "url": "https://cs.ics.uci.edu/faculty/",
        "source_type": "ics_faculty",
        "display_name": "UCI ICS Faculty Listing",
        "professor_hint": None,
    },
    # RMP individual professor pages — JS-rendered.
    # Save rendered HTML to data/raw/<slug>.html via Playwright, then re-run.
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
    {
        "slug": "rmp_uci_cs",
        "url": "https://www.ratemyprofessors.com/search/professors/1074?q=*&did=11",
        "source_type": "rmp",
        "display_name": "RMP: UCI CS Professors",
        "professor_hint": None,
    },
    # Uloop — also JS-rendered; same process as RMP above
    {
        "slug": "uloop_cs",
        "url": "https://uci.uloop.com/professors?department_id=1534",
        "source_type": "uloop",
        "display_name": "Uloop: UCI CS Professors",
        "professor_hint": None,
    },
]

# These source types need a JS renderer — skip unless a cached HTML file exists
JS_ONLY_TYPES = {"rmp", "uloop"}

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    text:         str
    source_type:  str
    source_name:  str
    source_url:   str
    professor:    Optional[str]
    course:       Optional[str]
    chunk_index:  int
    chunk_id:     str

# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_raw(url: str, slug: str) -> Optional[str]:
    """
    Return the raw text for a source.

    Handles three cases:
      1. file:// URL  — read the local file directly (txt or html)
      2. Cached HTML  — data/raw/<slug>.html already exists, load it
      3. Remote URL   — HTTP GET, save result to data/raw/<slug>.html
    """
    os.makedirs(RAW_DIR, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Case 1: local file path                                              #
    # ------------------------------------------------------------------ #
    if url.startswith("file://"):
        # Strip scheme and normalise separators for Windows
        local_path = url[len("file://"):].replace("/", os.sep)
        print(f"  [local] {local_path}")
        if not os.path.exists(local_path):
            print(f"  [ERROR] File not found: {local_path}")
            print(f"          Expected: {os.path.abspath(local_path)}")
            return None
        with open(local_path, encoding="utf-8") as f:
            return f.read()

    # ------------------------------------------------------------------ #
    # Case 2: cached copy on disk                                          #
    # ------------------------------------------------------------------ #
    cached = os.path.join(RAW_DIR, f"{slug}.html")
    if os.path.exists(cached):
        print(f"  [cache] {cached}")
        with open(cached, encoding="utf-8") as f:
            return f.read()

    # ------------------------------------------------------------------ #
    # Case 3: fetch from network                                           #
    # ------------------------------------------------------------------ #
    print(f"  [fetch] {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        raw = resp.text
    except requests.RequestException as e:
        print(f"  [ERROR] {e}")
        return None

    with open(cached, "w", encoding="utf-8") as f:
        f.write(raw)
    time.sleep(REQUEST_DELAY)
    return raw

# ---------------------------------------------------------------------------
# Cleaning utilities
# ---------------------------------------------------------------------------

BOILERPLATE = [
    "Sign in", "Log in", "Create account", "Cookie Policy", "Privacy Policy",
    "Terms of Service", "Rate My Professors", "All Rights Reserved", "©",
    "Subscribe", "Newsletter", "JavaScript is disabled", "Enable JavaScript",
    "Advertisement", "Sponsored", "Skip to content", "Back to top",
    "Load more", "Show more comments",
]

def strip_boilerplate(text: str) -> str:
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or len(s) < 15:
            continue
        if any(b.lower() in s.lower() for b in BOILERPLATE):
            continue
        lines.append(s)
    return "\n".join(lines)

def normalize_ws(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def remove_md_links(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(https?://[^\)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    return text

# ---------------------------------------------------------------------------
# Source-specific cleaners
# ---------------------------------------------------------------------------

def clean_reddit_txt(raw: str) -> str:
    """Clean plain-text Reddit content (manually copy-pasted or saved as .txt)."""
    text = remove_md_links(raw)
    text = strip_boilerplate(text)
    return normalize_ws(text)

def clean_reddit_html(raw: str) -> str:
    """Clean a saved Reddit HTML page."""
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup.find_all(["nav", "footer", "script", "style",
                               "aside", "header", "iframe", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(
        r"(actionbar|awardings|vote|ads|sidebar|community-info|nav|"
        r"subreddit-info|join|subscribe|search|login|signup|cookie|"
        r"flair|award|trophy|banner|icon|share|report)", re.I
    )):
        tag.decompose()
    body = soup.find("body") or soup
    text = body.get_text(separator="\n")
    text = strip_boilerplate(text)
    text = remove_md_links(text)
    text = normalize_ws(text)
    lines = [l for l in text.split("\n") if len(l.split()) >= 4]
    return "\n".join(lines)

def clean_ics_faculty(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup.find_all(["nav", "footer", "script", "style", "aside", "header"]):
        tag.decompose()
    main = soup.find("main") or soup.find("div", id="content") or soup.find("body")
    text = (main or soup).get_text(separator="\n")
    return normalize_ws(strip_boilerplate(text))

def clean_rmp_html(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup.find_all(["nav", "footer", "script", "style", "header", "aside"]):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(
        r"(navbar|sidebar|ad|cookie|banner|modal|search-bar|filter)", re.I
    )):
        tag.decompose()
    main = (soup.find("main")
            or soup.find("div", class_=re.compile("content|results", re.I))
            or soup.find("body"))
    text = (main or soup).get_text(separator="\n")
    text = strip_boilerplate(text)
    text = normalize_ws(text)
    lines = [l for l in text.split("\n") if len(l.split()) >= 3]
    return "\n".join(lines)

def clean_document(raw: str, source_type: str) -> str:
    if source_type == "reddit":
        # Detect whether this is plain text or HTML
        if raw.strip().startswith("<"):
            return clean_reddit_html(raw)
        return clean_reddit_txt(raw)
    elif source_type == "ics_faculty":
        return clean_ics_faculty(raw)
    elif source_type == "rmp":
        return clean_rmp_html(raw)
    else:
        return clean_rmp_html(raw)   # generic HTML fallback

# ---------------------------------------------------------------------------
# Professor / course extraction
# ---------------------------------------------------------------------------

COURSE_RE = re.compile(
    r"\b(ICS|CS|COMPSCI|IN4MATX|I&C\s*SCI)\s*(\d{1,3}[A-Z]?)\b", re.IGNORECASE
)

KNOWN_PROFS = [
    "Ahmed", "Thornton", "Klefstad", "Shindler", "Pattis", "Dillencourt",
    "Frost", "Goodrich", "Irani", "Lathrop", "Lueker", "Petzold",
    "Eppstein", "Kay", "Epstein", "Varanasi", "Dutt", "Gupta", "Sherwood",
]
PROF_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in KNOWN_PROFS) + r")\b", re.IGNORECASE
)

def extract_professor(text: str, hint: Optional[str]) -> Optional[str]:
    if hint:
        return hint
    m = PROF_RE.search(text)
    return m.group(0).capitalize() if m else None

def extract_course(text: str) -> Optional[str]:
    m = COURSE_RE.search(text)
    if not m:
        return None
    dept = m.group(1).upper().replace(" ", "").replace("&", "")
    return f"{dept} {m.group(2).upper()}"

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, source: dict) -> list[Chunk]:
    if not text.strip():
        return []

    chunks, start, index, seen = [], 0, 0, set()

    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            boundary = max(
                text.rfind(". ", start, end),
                text.rfind("! ", start, end),
                text.rfind("? ", start, end),
                text.rfind("\n",  start, end),
            )
            if boundary > start + CHUNK_SIZE // 2:
                end = boundary + 1

        piece = text[start:end].strip()

        if len(piece) >= MIN_CHUNK_LEN:
            dedup_key = piece[:80]
            if dedup_key not in seen:
                seen.add(dedup_key)
                cid = hashlib.md5(piece.encode()).hexdigest()[:12]
                chunks.append(Chunk(
                    text        = piece,
                    source_type = source["source_type"],
                    source_name = source["display_name"],
                    source_url  = source["url"],
                    professor   = extract_professor(piece, source.get("professor_hint")),
                    course      = extract_course(piece),
                    chunk_index = index,
                    chunk_id    = f"{source['slug']}_{index}_{cid}",
                ))
                index += 1

        start = end - CHUNK_OVERLAP
        if start >= len(text):
            break

    return chunks

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(RAW_DIR,     exist_ok=True)
    os.makedirs(CLEANED_DIR, exist_ok=True)

    all_chunks: list[Chunk] = []
    skipped: list[str]      = []

    for source in SOURCES:
        slug  = source["slug"]
        stype = source["source_type"]
        print(f"\n{'='*60}")
        print(f"Processing: {source['display_name']}")

        # JS-rendered sources: only process if a cached HTML file already exists
        if stype in JS_ONLY_TYPES:
            cached_html = os.path.join(RAW_DIR, f"{slug}.html")
            if not os.path.exists(cached_html):
                print(f"  [SKIP] Needs JS renderer.")
                print(f"         Save rendered HTML to: {cached_html}")
                skipped.append(source["display_name"])
                continue
            print(f"  [cache] {cached_html}")

        # Fetch / load
        raw = fetch_raw(source["url"], slug)
        if raw is None:
            print(f"  [SKIP] Could not load {slug}")
            continue

        # Clean
        cleaned = clean_document(raw, stype)
        if not cleaned.strip():
            print(f"  [WARN] Cleaning produced empty output for {slug}")
            continue

        cleaned_path = os.path.join(CLEANED_DIR, f"{slug}.txt")
        with open(cleaned_path, "w", encoding="utf-8") as f:
            f.write(cleaned)
        print(f"  [clean] {len(cleaned):,} chars → {cleaned_path}")

        # Chunk
        chunks = chunk_text(cleaned, source)
        all_chunks.extend(chunks)
        print(f"  [chunk] {len(chunks)} chunks")

    # Save all chunks
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")

    print(f"\n{'='*60}")
    print(f"DONE: {len(all_chunks)} total chunks → {CHUNKS_FILE}")

    if skipped:
        print(f"\nSkipped (need Playwright to render JS):")
        for name in skipped:
            print(f"  • {name}")
        print("\n  pip install playwright && playwright install chromium")
        print("  Render each page and save HTML to data/raw/<slug>.html, then re-run.")


if __name__ == "__main__":
    main()