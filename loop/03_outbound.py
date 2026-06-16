#!/usr/bin/env python3
"""
Phase 03: Warm Outbound
Generates warm email and LinkedIn DM copy for Tier 1 (Hot) and Tier 2 (Warm) engagers.
References their specific content engagement — the core of founder-led warm outbound.

Tier 1: Founder sends manually. Output is a draft to review + send.
Tier 2: Goes into sequence. Output is CSV for Smartlead/Instantly import.

Usage:
    python loop/03_outbound.py --input scored_engagers.csv --output outbound.csv --sender "Rasul" --sender-title "GTM Engineer"
    python loop/03_outbound.py --input scored_engagers.csv --tier 1  # only Tier 1
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import requests


MINIMAX_API_URL = "https://api.minimaxi.chat/v1/chat/completions"
MINIMAX_MODEL = "MiniMax-Text-01"

EMAIL_SYSTEM = """Write a warm cold email. The sender is a founder/GTM engineer. The prospect just engaged with their LinkedIn content.

Rules:
- Open with ONE observation about what they engaged with + why it's relevant to their role
- Bridge to the sender's specific experience (use the context given)
- CTA: one easy ask, under 8 words
- Total: under 100 words
- No "I hope this finds you well". No exclamation marks. No "congrats on".
- Sound like a real person. Not a vendor.

Return JSON only:
{"subject": "...", "body": "..."}"""

DM_SYSTEM = """Write a LinkedIn DM. Founder-to-founder or founder-to-buyer tone.

Rules:
- Max 3 sentences
- Reference their engagement with the specific post
- No pitch in the DM. Just open a conversation.
- Ends with a question or a low-friction observation

Return JSON only:
{"dm": "..."}"""


def call_minimax(prompt: str, system: str) -> str:
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        raise ValueError("MINIMAX_API_KEY not set")

    resp = requests.post(
        MINIMAX_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": MINIMAX_MODEL, "messages": [{"role": "user", "content": prompt}],
              "max_tokens": 400, "temperature": 0.75},
        timeout=30,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text.strip()


def parse_json_response(raw: str) -> dict:
    """Extract JSON from model response, handling markdown fences."""
    text = re.sub(r"```json?\s*", "", raw).replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return {"error": raw}


def generate_email(row: dict, sender: str, sender_title: str, sender_context: str) -> dict:
    prompt = (
        f"Prospect: {row.get('first_name')} {row.get('full_name', '')}, "
        f"{row.get('title')} at {row.get('company')}\n"
        f"They engaged with: {row.get('engagement_type')} on a post about: {row.get('post_topic') or 'GTM / outbound strategy'}\n"
        f"Company: {row.get('industry', '')} industry, ~{row.get('employees', '?')} employees\n"
        f"Sender: {sender}, {sender_title}\n"
        f"Sender context: {sender_context}\n\n"
        "Write the warm email."
    )
    raw = call_minimax(prompt, EMAIL_SYSTEM)
    return parse_json_response(raw)


def generate_dm(row: dict, sender: str) -> dict:
    prompt = (
        f"Prospect: {row.get('first_name')}, {row.get('title')} at {row.get('company')}\n"
        f"They {row.get('engagement_type', 'liked')} your post about: {row.get('post_topic') or 'GTM strategy'}\n"
        f"Sender: {sender}\n\n"
        "Write the LinkedIn DM."
    )
    raw = call_minimax(prompt, DM_SYSTEM)
    return parse_json_response(raw)


def run(
    input_csv: str,
    output_csv: str,
    sender: str,
    sender_title: str,
    sender_context: str,
    tier_filter: int = 0,
    delay: float = 1.0,
) -> None:
    with open(input_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if tier_filter:
        rows = [r for r in rows if str(r.get("tier", "")) == str(tier_filter)]
        print(f"Filtered to Tier {tier_filter}: {len(rows)} engagers")

    # Only generate outbound for Tier 1 and 2
    rows = [r for r in rows if str(r.get("tier", "3")) in ("1", "2")]
    print(f"Generating outbound for {len(rows)} Hot + Warm engagers...")

    output_fields = [
        "full_name", "first_name", "company", "title", "email", "linkedin_url",
        "tier", "tier_label", "icp_score", "engagement_type", "post_topic",
        "email_subject", "email_body", "linkedin_dm", "recommended_play",
    ]

    results = []
    for i, row in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] {row.get('first_name')} @ {row.get('company')} (Tier {row.get('tier')})...", end=" ", flush=True)
        try:
            email = generate_email(row, sender, sender_title, sender_context)
            dm = generate_dm(row, sender)
            row["email_subject"] = email.get("subject", "")
            row["email_body"] = email.get("body", "")
            row["linkedin_dm"] = dm.get("dm", "")
            print("done")
        except Exception as e:
            print(f"ERROR: {e}")
            row["email_subject"] = ""
            row["email_body"] = str(e)
            row["linkedin_dm"] = ""

        results.append(row)
        if i < len(rows):
            time.sleep(delay)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDone. {len(results)} warm sequences generated → {output_csv}")
    t1 = sum(1 for r in results if str(r.get("tier")) == "1")
    t2 = sum(1 for r in results if str(r.get("tier")) == "2")
    print(f"Tier 1 (founder sends manually): {t1}")
    print(f"Tier 2 (goes into sequence):     {t2}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 03: Generate warm outbound email + DM via MiniMax")
    parser.add_argument("--input", required=True, help="Scored engagers CSV from Phase 02")
    parser.add_argument("--output", default="outbound_sequences.csv")
    parser.add_argument("--sender", required=True, help="Your first name")
    parser.add_argument("--sender-title", default="GTM Engineer")
    parser.add_argument("--sender-context", default=(
        "GTM Engineer who has built outbound systems generating $550K+ revenue. "
        "Specializes in signal-led outbound and AI-powered GTM infrastructure."
    ))
    parser.add_argument("--tier", type=int, default=0, help="Filter to specific tier (1 or 2). Default: both.")
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    run(
        input_csv=args.input,
        output_csv=args.output,
        sender=args.sender,
        sender_title=args.sender_title,
        sender_context=args.sender_context,
        tier_filter=args.tier,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
