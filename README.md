# Learning Library Steward

An autonomous AI agent that discovers, evaluates, and curates learning resources for a rigorously curated research library about how humans learn, teach, design, assess, coach, and develop.

---

## What This Does

Every Monday at 09:00 UTC, this agent runs a sweep:

1. **Discovers** recent peer-reviewed papers via the [Exa](https://exa.ai) search API
2. **Evaluates** each candidate with Google's [Gemini](https://ai.google.dev) model
3. **Scores** them on Authority, Evidence, Relevance, Currency, and Uniqueness
4. **Inserts** verified candidates into the `review_queue` table in Supabase
5. **Waits** for human review — nothing enters the library without approval

The library itself lives at the [Learning Library](https://github.com/Indermanithapa/learning-library-steward) — a companion web app backed by Supabase.

---

## Why This Exists

The learning field produces thousands of papers, frameworks, tools, and platforms every year. No single curator can track it all. But quality matters more than quantity — a library is only as good as what it *excludes*.

This agent handles the discovery work. It never decides what enters the library. That's a human job, and the design is intentional: **AI triages. Humans decide.**

---

## Architecture
┌─────────────────────────────────────────────────────────────┐
│ GitHub Actions (weekly cron: Monday 09:00 UTC) │
│ │
│ steward.py │
│ │ │
│ ├──▶ Exa API → discover recent research papers │
│ ├──▶ Gemini API → evaluate, score, summarize │
│ └──▶ Supabase → insert into review_queue │
│ │
└─────────────────────────────────────────────────────────────┘
│
▼
┌──────────────────┐
│ /review UI │
│ (Human review) │
└──────────────────┘
│
Approve / Reject / Defer
│
▼
┌──────────────────┐
│ Library (live) │
└──────────────────┘

---

## The Domain Rotation

The library covers 8 locked domains. Each week, the agent sweeps one, rotating through the full list every 8 weeks:

1. Learning Sciences
2. Teaching & Pedagogy
3. Learning Design
4. Assessment & Evaluation
5. Organizational Learning & Talent
6. Coaching & Mentoring
7. Inclusive & Special Education
8. Research Methods & Evidence Synthesis

The target domain is calculated from the current ISO week number:
domain_index = (week_number - 1) mod 8

---

## The Five-Stage Lifecycle

Every candidate moves through five states:

| Stage          | Meaning                        | Who Decides       |
|----------------|--------------------------------|-------------------|
| **Discovered** | Exa found it                   | Agent (automatic) |
| **Suggested**  | Agent recommends it            | Agent (automatic) |
| **Verified**   | Passed source-quality criteria | Agent (automatic) |
| **Approved**   | Added to the library           | Human (manual)    |
| **Retired**    | Superseded or outdated         | Human (manual)    |

Nothing enters the public library without human approval.

---

## What Gets Included

- Peer-reviewed research and systematic reviews
- Academic textbooks and university publications
- University open educational resources
- Government and public-sector education research
- Professional association publications and standards
- Institutional reports from recognized research organizations
- Expert practitioner articles from recognized voices

## What Gets Excluded

- Wikipedia as a primary source
- Commercial content without independent credibility
- AI-generated content without human authorship
- SEO-optimized blog spam
- Content outside the meta-domain of learning
- Vendor product pages (those go in a separate Tools Directory)

---

## Setup

### Prerequisites

- A GitHub account (free)
- An [Exa](https://exa.ai) API key (free tier available)
- A Google [Gemini](https://ai.google.dev) API key (free tier available)
- A [Supabase](https://supabase.com) project with the `review_queue` table

### GitHub Secrets

Add these four secrets in **Settings → Secrets and variables → Actions**:

| Secret Name      | Where to Find It                                                    |
|------------------|---------------------------------------------------------------------|
| `EXA_API_KEY`    | From your Exa dashboard                                             |
| `GEMINI_API_KEY` | Google AI Studio → Get API Key                                      |
| `SUPABASE_URL`   | Supabase → Settings → API → Project URL (full URL, with `https://`) |
| `SUPABASE_KEY`   | Supabase → Settings → API → anon public key                         |

### Running Locally

```bash
git clone https://github.com/Indermanithapa/learning-library-steward.git
cd learning-library-steward
pip install -r requirements.txt

export EXA_API_KEY="your-exa-key"
export GEMINI_API_KEY="your-gemini-key"
export SUPABASE_URL="https://yourproject.supabase.co"
export SUPABASE_KEY="your-anon-key"

python steward.py
