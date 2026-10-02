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
from datetime import datetime

# ── Environment variables (set in GitHub Secrets) ──
EXA_API_KEY = os.environ["EXA_API_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

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


def get_week_number():
    """Return the ISO week number of the current year."""
    return datetime.utcnow().isocalendar()[1]


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
                datetime.utcnow().replace(year=datetime.utcnow().year - 1).isoformat() + "Z"
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
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={GEMINI_API_KEY}",
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


def insert_to_supabase(candidate):
    """Insert a scored candidate into the review_queue table."""
    row = {
        "title": candidate.get("title", ""),
        "url": candidate.get("url", ""),
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
    response.raise_for_status()
    return True


def main():
    week_num = get_week_number()
    domain = get_target_domain(week_num)
    query = DOMAIN_QUERIES[domain]

    print(f"[Week {week_num}] Target domain: {domain}")
    print(f"[Search] Query: {query}")

    candidates = search_exa(query)
    print(f"[Exa] Found {len(candidates)} candidates")

    inserted = 0
    for i, candidate in enumerate(candidates[:5], 1):
        try:
            print(f"[Gemini] Evaluating candidate {i}/{min(len(candidates), 5)}...")
            evaluated = evaluate_with_gemini(candidate, domain)

            if not evaluated.get("url_verified", False):
                print(f"[Skip] URL not verified: {evaluated.get('title', '')[:60]}")
                continue

            insert_to_supabase(evaluated)
            inserted += 1
            print(f"[Insert] ✅ {evaluated.get('title', '')[:60]}")

        except Exception as e:
            print(f"[Error] Candidate {i}: {e}")
            continue

    print(f"\n[Done] Inserted {inserted} candidates into review_queue")

 # Space out Gemini calls to avoid rate limits
        time.sleep(15)

if __name__ == "__main__":
    main()
