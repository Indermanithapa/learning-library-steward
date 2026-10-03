"""
Send pending review_queue candidates to Telegram with inline buttons.
Runs after steward.py in the weekly sweep workflow.
"""

import os
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_telegram_message(text, reply_markup=None, disable_preview=True, html_mode=False):
    """Send a single message to the configured chat."""
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": disable_preview,
    }
    if html_mode:
        payload["parse_mode"] = "HTML"
    else:
        payload["parse_mode"] = "Markdown"

    if reply_markup:
        payload["reply_markup"] = reply_markup

    r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=30)
    if not r.ok:
        print(f"[Telegram] sendMessage failed: {r.status_code} {r.text}")
    r.raise_for_status()
    return r.json()


def send_candidate(candidate):
    """Send one candidate with full metadata and three inline buttons."""

    # --- Top action bar ---
    action = (candidate.get("suggested_action") or "add").upper()
    confidence = (candidate.get("confidence_level") or "medium").capitalize()
    comparison = (candidate.get("comparison_type") or "new").capitalize()

    action_emoji = {
        "ADD": "🎯",
        "REPLACE": "🔄",
        "SUPPLEMENT": "➕",
        "FLAG": "🚩",
        "REJECT": "❌",
        "DEFER": "⏸",
    }.get(action, "🎯")

    # --- Header line ---
    top = f"{action_emoji} <b>ACTION: {action}</b> • {confidence} confidence • Comparison: {comparison}"

    # --- Title ---
    title = (candidate.get("title") or "Untitled")[:180]
    title_line = f"<b>{title}</b>"

    # --- Author / Institution / Year ---
    author = candidate.get("author") or "Unknown"
    institution = candidate.get("institution") or "Unknown institution"
    year = candidate.get("year") or "—"
    byline = f"👤 {author} • 🏛 {institution} • 📅 {year}"

    # --- Scores ---
    scores = {
        "Authority": candidate.get("authority_score"),
        "Evidence": candidate.get("evidence_score"),
        "Relevance": candidate.get("relevance_score"),
        "Currency": candidate.get("currency_score"),
        "Uniqueness": candidate.get("uniqueness_score"),
    }

    score_lines = []
    total = 0
    count = 0
    for name, val in scores.items():
        if val is not None:
            score_lines.append(f"  • {name}: <b>{val}</b>")
            total += float(val)
            count += 1

    if count > 0:
        overall = round(total / count, 1)
        scores_block = (
            "📊 <b>Rubric Scores</b>\n"
            + "\n".join(score_lines)
            + f"\n  ⭐ <b>Overall: {overall} / 10</b>"
        )
    else:
        scores_block = "📊 <b>Rubric Scores:</b> not scored"

    # --- Domain + Evidence ---
    domain = candidate.get("proposed_domain") or "N/A"
    evidence = candidate.get("proposed_evidence_level") or "N/A"
    proposed_block = f"🏷 <b>Proposed:</b> {domain} · {evidence}"

    # --- Summary ---
    summary = (candidate.get("ai_summary") or "No summary available.")[:500]

    # --- Reasoning ---
    reasoning = (candidate.get("ai_reasoning") or "No reasoning provided.")[:500]

    # --- URL ---
    url = candidate.get("url") or ""
    url_line = f'🔗 <a href="{url}">Read the paper</a>' if url else ""

    # --- Assemble ---
    text = "\n\n".join(filter(None, [
        top,
        title_line,
        byline,
        "━━━━━━━━━━━━━━━━━━━━",
        scores_block,
        proposed_block,
        "━━━━━━━━━━━━━━━━━━━━",
        f"💡 <b>AI Summary</b>\n{summary}",
        f"🧠 <b>AI Curatorial Reasoning</b>\n{reasoning}",
        url_line,
    ]))

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{candidate['id']}"},
            {"text": "❌ Reject",  "callback_data": f"reject:{candidate['id']}"},
            {"text": "⏸ Defer",   "callback_data": f"defer:{candidate['id']}"},
        ]]
    }

    send_telegram_message(text, reply_markup=keyboard, html_mode=True)


def main():
    # Fetch pending candidates
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/review_queue",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
        params={
            "status": "eq.pending",
            "order": "created_at.desc",
            "limit": "10",
        },
        timeout=30,
    )
    r.raise_for_status()
    candidates = r.json()

    if not candidates:
        send_telegram_message("📭 No pending candidates this week.")
        print("[Telegram] No pending candidates — sent empty notice.")
        return

    # Header message
    send_telegram_message(
        f"📚 *Weekly Library Review*\n\n"
        f"{len(candidates)} candidate(s) awaiting your decision."
    )

    # One message per candidate
    for c in candidates:
        try:
            send_candidate(c)
            print(f"[Telegram] Sent: {c.get('title', '')[:60]}")
        except Exception as e:
            print(f"[Telegram] Error sending {c.get('id')}: {e}")

    print(f"[Telegram] Done — sent {len(candidates)} candidates.")


if __name__ == "__main__":
    main()
