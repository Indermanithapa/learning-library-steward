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


def send_telegram_message(text, reply_markup=None, disable_preview=True):
    """Send a single message to the configured chat."""
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": disable_preview,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def send_candidate(candidate):
    """Send one candidate with three inline buttons."""
    title = candidate.get("title", "Untitled")[:120]
    author = candidate.get("author", "Unknown author")
    institution = candidate.get("institution", "")
    year = candidate.get("year", "")
    url = candidate.get("url", "")

    text = (
        f"📄 *{title}*\n\n"
        f"👤 {author}\n"
        f"🏛 {institution}\n"
        f"📅 {year}\n\n"
        f"*Domain:* {candidate.get('proposed_domain', 'N/A')}\n"
        f"*Evidence:* {candidate.get('proposed_evidence_level', 'N/A')}\n\n"
        f"*Summary:*\n{(candidate.get('ai_summary') or '')[:350]}\n\n"
        f"[Read the paper]({url})"
    )

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{candidate['id']}"},
            {"text": "❌ Reject",  "callback_data": f"reject:{candidate['id']}"},
            {"text": "⏸ Defer",   "callback_data": f"defer:{candidate['id']}"},
        ]]
    }

    send_telegram_message(text, reply_markup=keyboard)


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
