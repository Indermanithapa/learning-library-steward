# Setup Overview

This document describes what The Learning Library is made of. It is intentionally high-level. If you're planning to fork or self-host, you'll want to read the code alongside this overview.

---

## What You'll Need

The pipeline runs on free-tier services. To replicate it end-to-end, you'll need accounts on:

| Service | Purpose |
|---|---|
| [Supabase](https://supabase.com) | Database, edge functions, auth |
| [Exa](https://exa.ai) | Research paper discovery |
| [Google AI Studio](https://aistudio.google.com) | Gemini API for evaluation |
| [Telegram](https://telegram.org) | Bot for human review |
| [GitHub](https://github.com) | Hosting the code, running the weekly schedule |

---

## How the Pipeline Works

At a high level:

1. **Discover** — A weekly GitHub Action calls Exa to find recent peer-reviewed papers
2. **Evaluate** — Each paper is scored by Gemini on 5 dimensions (authority, evidence, relevance, currency, uniqueness)
3. **Stage** — Scored candidates are inserted into a `review_queue` table in Supabase
4. **Notify** — A Telegram bot sends each candidate to the maintainer with Approve / Reject / Defer buttons
5. **Commit** — Approved candidates are written to the public `resources` table
6. **Display** — The frontend reads from Supabase and renders the library, concept graph, and tools

---

## Where Things Live

| File | What It Does |
|---|---|
| `steward.py` | The weekly discovery agent — Exa search + Gemini evaluation + Supabase insert |
| `send_to_telegram.py` | Sends staged candidates to Telegram with action buttons |
| `supabase_migration.sql` | Database schema and seed data |
| `supabase/functions/telegram-steward/index.ts` | Edge function that receives button taps and writes decisions back to Supabase |
| `.github/workflows/weekly-sweep.yml` | Schedules the whole thing every Monday at 09:00 UTC |

---

## Running It Locally

```bash
git clone https://github.com/Indermanithapa/learning-library-steward.git
cd learning-library-steward
pip install -r requirements.txt
python steward.py
```

Environment variables needed (see the code for exact names):

- Exa API key
- Gemini API key
- Supabase project URL
- Supabase publishable key
- Supabase service key

---

## The Weekly Schedule

The pipeline runs automatically on GitHub Actions. You can also trigger it manually from the **Actions** tab in the repository.

Once triggered, it takes roughly 2 minutes to complete. Approved candidates appear in the library within seconds of the Telegram approval.

---

## A Note on Scope

This repository contains the **backend pipeline only**. The public-facing frontend is hosted separately at [the-learning-library.ai.studio](https://the-learning-library.ai.studio/) and connects to the same Supabase database.

---

## Questions

If something isn't clear from the code and this overview, open a GitHub issue.

---

**Understand the landscape. Find the depth.**
