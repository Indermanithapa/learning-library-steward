"""
Learning Library Steward
========================
Weekly sweep agent: discovers new learning resources via Exa,
evaluates them with Gemini, inserts candidates into Supabase review_queue.

Runs on GitHub Actions on a weekly cron schedule.
"""

import os
import json
import requests
import time
import re
from urllib.parse import urlsplit, urlunsplit
from datetime import datetime, timezone

# ── Environment variables (set in GitHub Secrets) ──
EXA_API_KEY = os.environ["EXA_API_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]  # Service-role key; GitHub Actions secret only.

# ── The 8 locked domains ──
DOMAINS = [
    "Learning Sciences",
    "Teaching & Pedagogy",
    "Learning Design",
    "Assessment & Evaluation",
    "Organizational Learning & Talent",
    "Coaching & Mentoring",
    "Inclusive & Special Education",
    "Research Methods & Evidence Synthesis",
]

# ── Domain-specific search queries (one per domain) ──
DOMAIN_QUERIES = {
    "Learning Sciences": "new peer-reviewed research on cognitive science, memory, motivation, or educational psychology in learning",
    "Teaching & Pedagogy": "new peer-reviewed research on teaching methods, classroom practice, formative assessment, or feedback",
    "Learning Design": "new peer-reviewed research on instructional design, curriculum, multimedia learning, or microlearning",
    "Assessment & Evaluation": "new peer-reviewed research on assessment, evaluation models, Kirkpatrick, Phillips, or learning analytics",
    "Organizational Learning & Talent": "new peer-reviewed research on workplace learning, talent development, or leadership development",
    "Coaching & Mentoring": "new peer-reviewed research on coaching models, mentoring, or facilitation effectiveness",
    "Inclusive & Special Education": "new peer-reviewed research on UDL, accessibility, neurodiversity, or inclusive education",
    "Research Methods & Evidence Synthesis": "new peer-reviewed methodology paper on meta-analysis, systematic review methods, or research design in education",
}


# Multiple angles per domain help the steward replace duplicates rather than stop early.
# Keep the weekly domain rotation frozen; only broaden discovery within that domain.
DOMAIN_QUERY_VARIANTS = {
    "Learning Sciences": [
        "recent peer-reviewed empirical studies on memory, retrieval practice, spacing, and long-term retention",
        "recent peer-reviewed research on motivation, attention, cognitive load, and self-regulated learning",
        "recent systematic reviews or meta-analyses in cognitive science and educational psychology",
    ],
    "Teaching & Pedagogy": [
        "recent peer-reviewed empirical research on formative assessment, feedback, and student learning outcomes",
        "recent peer-reviewed studies of classroom teaching strategies, active learning, and instructional practice",
        "recent systematic reviews or meta-analyses on teaching methods and pedagogical effectiveness",
    ],
    "Learning Design": [
        "recent peer-reviewed research on instructional design models and evidence-based curriculum design",
        "recent empirical studies on multimedia learning, microlearning, and digital learning design",
        "recent systematic reviews on instructional design, learning experience design, or online learning design",
    ],
    "Assessment & Evaluation": [
        "recent peer-reviewed research on assessment validity, rubric design, and formative or authentic assessment",
        "recent empirical research on learning evaluation, training transfer, and workplace learning outcomes",
        "recent systematic reviews on learning analytics, educational measurement, or program evaluation",
    ],
    "Organizational Learning & Talent": [
        "recent peer-reviewed empirical studies on workplace learning, skill development, and training transfer",
        "recent peer-reviewed research on leadership development, talent development, and organizational capability",
        "recent systematic reviews on employee learning, professional development, or learning culture",
    ],
    "Coaching & Mentoring": [
        "recent peer-reviewed empirical research on coaching effectiveness and measurable developmental outcomes",
        "recent peer-reviewed studies on mentoring, feedback conversations, and professional development",
        "recent systematic reviews or meta-analyses on coaching, mentoring, or facilitation interventions",
    ],
    "Inclusive & Special Education": [
        "recent peer-reviewed research on Universal Design for Learning and accessible instructional design",
        "recent empirical studies on inclusive education, neurodiversity, and learner accommodations",
        "recent systematic reviews on disability inclusion, special education, or accessibility in learning",
    ],
    "Research Methods & Evidence Synthesis": [
        "recent peer-reviewed methodological papers on systematic reviews and evidence synthesis in education",
        "recent research on meta-analysis methods, publication bias, and evidence quality in learning research",
        "recent peer-reviewed methods research on education study design, reproducibility, or research reporting",
    ],
}

WEEKLY_TARGET = 10
MAX_UNIQUE_EVALUATIONS = 40
RESULTS_PER_QUERY = 15
MIN_QUALITY_AVERAGE = 7.0
QUALITY_SCORE_FIELDS = (
    "authority_score", "evidence_score", "relevance_score",
    "currency_score", "uniqueness_score",
)


def get_week_number():
    """Return the ISO week number of the current year."""
    return datetime.now(timezone.utc).isocalendar()[1]

def get_target_domain(week_num):
    """Map week number to a domain using the rotation formula."""
    idx = (week_num - 1) % 8
    return DOMAINS[idx]


def search_exa(query, num_results=8):
    """Search Exa for recent academic resources."""
    response = requests.post(
        "https://api.exa.ai/search",
        headers={
            "x-api-key": EXA_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "numResults": num_results,
            "type": "auto",
            "category": "research paper",
            "startPublishedDate": (
                datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year - 1).isoformat()
            ),
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json().get("results", [])


import time

def evaluate_with_gemini(candidate, domain, max_retries=3):
    """Score a candidate using Gemini with retry logic."""
    prompt = f"""You are the Learning Library Steward. Evaluate this candidate resource for a rigorously curated library.

TARGET DOMAIN: {domain}

CANDIDATE:
Title: {candidate.get('title', 'Unknown')}
URL: {candidate.get('url', '')}
Author: {candidate.get('author', 'Unknown')}
Published: {candidate.get('publishedDate', 'Unknown')}
Text excerpt: {candidate.get('text', '')[:2000]}

TASK:
1. Verify the URL is a direct link to this specific paper (not a journal homepage or search page).
2. Score on 5 dimensions (0-10 each): Authority, Evidence, Relevance, Currency, Uniqueness.
3. Write a 2-sentence summary and a 2-sentence reasoning.

Return ONLY a JSON object with these fields:
{{
  "title": "...",
  "url": "...",
  "author": "...",
  "institution": "...",
  "year": 2026,
  "proposed_domain": "{domain}",
  "proposed_evidence_level": "Peer-reviewed",
  "authority_score": 0,
  "evidence_score": 0,
  "relevance_score": 0,
  "currency_score": 0,
  "uniqueness_score": 0,
  "ai_summary": "...",
  "ai_reasoning": "...",
  "url_verified": true
}}

No commentary. Only the JSON object."""

    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_API_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.4,
                        "maxOutputTokens": 2048,
                        "responseMimeType": "application/json",
                    },
                },
                timeout=90,
            )

            if response.status_code == 503:
                wait_time = (attempt + 1) * 15  # 15s, 30s, 45s
                print(f"  [Retry] 503 from Gemini. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(text)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 503 and attempt < max_retries - 1:
                continue
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  [Retry] Attempt {attempt+1} failed: {e}")
                time.sleep(10)
                continue
            raise

    raise Exception(f"Gemini failed after {max_retries} attempts")


def canonicalize_url(url):
    """Mirror public.canonicalize_url(text) from the deployed SQL migration."""
    value = (url or "").strip().split("#", 1)[0]
    match = re.match(r"^(https?)://([^/?#]+)(.*)$", value, flags=re.IGNORECASE)
    if not match:
        return value
    scheme, authority, suffix = match.groups()
    authority = authority.lower()
    if authority.startswith("www."):
        authority = authority[4:]
    if "?" not in suffix:
        suffix = re.sub(r"/+$", "", suffix)
    return scheme.lower() + "://" + authority + suffix


def supabase_get_all(table, params, page_size=500):
    """Read every matching row in pages, even when the project has a row cap.

    PostgREST's Content-Range header reports the total matching row count. We use
    that total when available so a server-side page cap smaller than page_size
    does not make the lookup stop early.
    """
    rows = []
    offset = 0
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Range-Unit": "items",
        "Prefer": "count=exact",
    }

    while True:
        page_params = dict(params)
        page_params["limit"] = str(page_size)
        page_params["offset"] = str(offset)
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=headers,
            params=page_params,
            timeout=30,
        )
        response.raise_for_status()
        page = response.json()
        rows.extend(page)

        content_range = response.headers.get("Content-Range", "")
        total = None
        if "/" in content_range:
            total_text = content_range.rsplit("/", 1)[1].strip()
            if total_text.isdigit():
                total = int(total_text)

        if not page:
            break
        offset += len(page)
        if total is not None:
            if offset >= total:
                break
        else:
            # Without a numeric total, do not infer that a short page is final:
            # a server-side cap may return fewer than page_size rows. Request the
            # next offset and stop only when the server returns an empty page.
            continue

    return rows



def load_existing_canonical_urls():
    """Load existing approved-resource and review-history URLs once per run."""
    known = set()
    resources = supabase_get_all(
        "resources",
        {"select": "id,url,source_status", "source_status": "eq.approved", "order": "id.asc"},
    )
    for row in resources:
        canonical = canonicalize_url(row.get("url"))
        if canonical:
            known.add(canonical)

    queue_rows = supabase_get_all(
        "review_queue",
        {"select": "id,url,status", "order": "id.asc"},
    )
    for row in queue_rows:
        canonical = canonicalize_url(row.get("url"))
        if canonical:
            known.add(canonical)
    return known


def passes_quality_threshold(candidate):
    """Require a verified direct URL and a complete mean score of at least 7/10."""
    if not candidate.get("url_verified", False):
        return False, "URL not verified as a direct resource link"

    author = (candidate.get("author") or "").strip()
    if not author or author.lower() == "unknown":
        return False, "missing or unknown author"
    
    scores = []
    for field in QUALITY_SCORE_FIELDS:
        value = candidate.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False, f"missing or invalid score: {field}"
        if value < 0 or value > 10:
            return False, f"out-of-range score: {field}"
        scores.append(float(value))

    average = sum(scores) / len(scores)
    if average < MIN_QUALITY_AVERAGE:
        return False, f"quality average {average:.1f}/10 is below {MIN_QUALITY_AVERAGE:.1f}"
    return True, f"quality average {average:.1f}/10"


def candidate_already_exists(url):
    """Suppress URLs already in the approved library or anywhere in review history."""
    canonical = canonicalize_url(url)
    if not canonical:
        return True

    # Read every approved resource; do not assume a single request returns the whole table.
    resources = supabase_get_all(
        "resources",
        {"select": "id,url,source_status", "source_status": "eq.approved", "order": "id.asc"},
    )
    for resource in resources:
        if canonicalize_url(resource.get("url")) == canonical:
            print(f"[Skip] Already in approved library: {url}")
            return True

    # Any prior queue status is treated as history, including rejected candidates.
    # This intentionally prevents automatic rediscovery; manual re-review can be added later.
    queue_rows = supabase_get_all(
        "review_queue",
        {"select": "id,url,status", "order": "id.asc"},
    )
    for item in queue_rows:
        if canonicalize_url(item.get("url")) == canonical:
            print(f"[Skip] URL already exists in review history (status={item.get('status')}): {url}")
            return True
    return False


def insert_to_supabase(candidate):
    """Insert only candidates absent from both the approved library and review history."""
    url = candidate.get("url", "").strip()
    if not url:
        print("[Skip] Candidate has no URL")
        return False

    canonical = canonicalize_url(url)
    if canonical in known_urls:
        print(f"[Skip] Already present in loaded history: {url}")
        return False

    row = {
        "title": candidate.get("title", ""),
        "url": url,
        "author": candidate.get("author"),
        "institution": candidate.get("institution"),
        "year": str(candidate.get("year", "")),
        "proposed_domain": candidate.get("proposed_domain"),
        "proposed_evidence_level": candidate.get("proposed_evidence_level"),
        "authority_score": candidate.get("authority_score"),
        "evidence_score": candidate.get("evidence_score"),
        "relevance_score": candidate.get("relevance_score"),
        "currency_score": candidate.get("currency_score"),
        "uniqueness_score": candidate.get("uniqueness_score"),
        "ai_summary": candidate.get("ai_summary"),
        "ai_reasoning": candidate.get("ai_reasoning"),
        "suggested_action": "add",
        "confidence_level": "medium",
        "comparison_type": "new",
        "discovery_source": "exa_api",
        "status": "pending",
    }

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/review_queue",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json=row,
        timeout=30,
    )
    # A partial unique index is the final guard against simultaneous duplicate inserts.
    if response.status_code == 409:
        print(f"[Skip] Database uniqueness guard blocked duplicate: {url}")
        return False
    response.raise_for_status()
    return True


def main():
    week_num = get_week_number()
    domain = get_target_domain(week_num)
    queries = [DOMAIN_QUERIES[domain], *DOMAIN_QUERY_VARIANTS[domain]]

    print(f"[Week {week_num}] Target domain: {domain}")
    print(f"[Plan] Weekly target: {WEEKLY_TARGET} qualified new candidates")
    print(f"[Plan] Up to {len(queries)} focused queries; {RESULTS_PER_QUERY} results per query; "
          f"maximum {MAX_UNIQUE_EVALUATIONS} unique evaluations")

    # Fail closed: if the existing records cannot be read, do not evaluate or insert.
    try:
        known_urls = load_existing_canonical_urls()
    except Exception as e:
        print(f"[Fatal] Could not load existing resource/review URLs; refusing discovery inserts: {e}")
        raise
    print(f"[Dedup] Loaded {len(known_urls)} canonical URLs from approved resources and review history")

    seen_this_run = set()
    evaluated_count = 0
    inserted = 0
    duplicate_skips = 0
    quality_skips = 0
    failed_candidates = 0
    raw_found = 0

    for query_index, query in enumerate(queries, 1):
        if inserted >= WEEKLY_TARGET or evaluated_count >= MAX_UNIQUE_EVALUATIONS:
            break

        print(f"[Search {query_index}/{len(queries)}] {query}")
        try:
            candidates = search_exa(query, num_results=RESULTS_PER_QUERY)
        except Exception as e:
            failed_candidates += 1
            print(f"[Search Error] Query {query_index} failed: {e}")
            continue

        raw_found += len(candidates)
        print(f"[Exa] Query {query_index} found {len(candidates)} results")

        for candidate in candidates:
            if inserted >= WEEKLY_TARGET or evaluated_count >= MAX_UNIQUE_EVALUATIONS:
                break

            url = (candidate.get("url") or "").strip()
            canonical = canonicalize_url(url)
            if not canonical:
                duplicate_skips += 1
                print("[Skip] Search result has no usable URL")
                continue
            if canonical in seen_this_run:
                duplicate_skips += 1
                print(f"[Skip] Duplicate result within this run: {url}")
                continue
            seen_this_run.add(canonical)

            if canonical in known_urls:
                duplicate_skips += 1
                print(f"[Skip] Already in approved library or review history: {url}")
                continue

            evaluated_count += 1
            print(f"[Gemini] Evaluating unique candidate {evaluated_count}/{MAX_UNIQUE_EVALUATIONS}...")
            try:
                evaluated = evaluate_with_gemini(candidate, domain)
                evaluated_url = (evaluated.get("url") or url).strip()
                evaluated_canonical = canonicalize_url(evaluated_url)
                if not evaluated_canonical:
                    quality_skips += 1
                    print("[Skip] Gemini returned no usable URL")
                    continue

                # Recheck Gemini's URL, since it may differ from Exa's URL.
                if evaluated_canonical in known_urls or evaluated_canonical in seen_this_run:
                    # If Gemini's URL is the original candidate URL, seen_this_run is expected;
                    # only treat it as duplicate when it differs from the Exa URL.
                    if evaluated_canonical != canonical:
                        duplicate_skips += 1
                        print(f"[Skip] Gemini URL already seen or present in history: {evaluated_url}")
                        continue

                passes, reason = passes_quality_threshold(evaluated)
                if not passes:
                    quality_skips += 1
                    print(f"[Skip] Quality gate: {reason} — {evaluated.get('title', '')[:80]}")
                    continue

                # Preserve the URL checked by Gemini as the proposed resource URL.
                evaluated["url"] = evaluated_url
                was_inserted = insert_to_supabase(evaluated, known_urls)
                if was_inserted:
                    inserted += 1
                    known_urls.add(evaluated_canonical)
                    print(f"[Insert] {inserted}/{WEEKLY_TARGET} — {evaluated.get('title', '')[:80]} ({reason})")
                else:
                    duplicate_skips += 1
            except Exception as e:
                failed_candidates += 1
                print(f"[Candidate Error] {url}: {e}")

            # Space out Gemini calls to reduce rate-limit risk.
            time.sleep(15)

    print("\n[Weekly Discovery Summary]")
    print(f"[Summary] Raw search results: {raw_found}")
    print(f"[Summary] Unique candidates evaluated: {evaluated_count}")
    print(f"[Summary] Duplicate candidates skipped: {duplicate_skips}")
    print(f"[Summary] Quality-gate skips: {quality_skips}")
    print(f"[Summary] Candidate/search errors: {failed_candidates}")
    print(f"[Summary] New candidates inserted: {inserted}/{WEEKLY_TARGET}")
    if inserted < WEEKLY_TARGET:
        print(f"[Shortfall] Target not reached; found {inserted} qualified new candidates. No quality threshold was lowered.")


if __name__ == "__main__":
    main()
