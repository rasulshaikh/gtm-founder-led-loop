#!/usr/bin/env python3
"""
Phase 04: Content Miner
Analyzes conversation notes or call transcripts and extracts:
  - Objections → post topics
  - Questions asked → educational content angles
  - Wins / results mentioned → proof post material
  - Patterns → series ideas

The loop compounds when conversations feed back into content.

Usage:
    python loop/04_content_miner.py --input conversations.txt
    python loop/04_content_miner.py --input calls.csv --field notes
    python loop/04_content_miner.py --text "They asked why they should use AI scoring vs manual..."
"""

import argparse
import json
import os
import re
import sys
import requests
from datetime import date
from pathlib import Path


MINIMAX_API_URL = "https://api.minimaxi.chat/v1/chat/completions"
MINIMAX_MODEL = "MiniMax-Text-01"

MINING_SYSTEM = """You analyze sales conversation notes and extract content ideas.

For each conversation, identify:
1. OBJECTIONS — things they pushed back on or questioned
2. QUESTIONS — what they genuinely wanted to understand
3. ASSUMPTIONS — things they assumed that were wrong
4. WINS — results or outcomes mentioned (yours or theirs)
5. PATTERNS — if you see a theme across multiple conversations

For each item, output a suggested LinkedIn post angle as a one-liner (punchy, founder voice, not corporate).

Return JSON:
{
  "objections": [{"raw": "...", "post_angle": "..."}],
  "questions": [{"raw": "...", "post_angle": "..."}],
  "assumptions": [{"raw": "...", "post_angle": "..."}],
  "wins": [{"raw": "...", "post_angle": "..."}],
  "patterns": ["..."],
  "top_post_idea": "The single best post idea from all of this, in one sentence."
}"""


def call_minimax(prompt: str) -> str:
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        raise ValueError("MINIMAX_API_KEY not set")

    resp = requests.post(
        MINIMAX_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": MINIMAX_MODEL, "max_tokens": 1000, "temperature": 0.6,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=40,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text.strip()


def parse_json_response(raw: str) -> dict:
    text = re.sub(r"```json?\s*", "", raw).replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return {"raw_output": raw}


def mine_text(conversation_text: str) -> dict:
    """Mine a block of text for content ideas."""
    prompt = (
        f"Sales conversation notes to analyze:\n\n{conversation_text}\n\n"
        "Extract content ideas from this."
    )
    raw = call_minimax(prompt)
    return parse_json_response(raw)


def format_output(result: dict, source: str = "") -> str:
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"CONTENT MINING REPORT — {date.today()}")
    if source:
        lines.append(f"Source: {source}")
    lines.append("=" * 60)

    if result.get("top_post_idea"):
        lines.append(f"\nTOP POST IDEA:\n  → {result['top_post_idea']}")

    for section, label in [
        ("objections", "OBJECTIONS → POST ANGLES"),
        ("questions", "QUESTIONS → EDUCATIONAL CONTENT"),
        ("assumptions", "WRONG ASSUMPTIONS → MYTH-BUSTING POSTS"),
        ("wins", "WINS → PROOF POSTS"),
    ]:
        items = result.get(section, [])
        if items:
            lines.append(f"\n{label}:")
            for item in items:
                if isinstance(item, dict):
                    lines.append(f"  Raw:   {item.get('raw', '')}")
                    lines.append(f"  Post:  {item.get('post_angle', '')}")
                    lines.append("")
                else:
                    lines.append(f"  {item}")

    patterns = result.get("patterns", [])
    if patterns:
        lines.append("PATTERNS / SERIES IDEAS:")
        for p in patterns:
            lines.append(f"  • {p}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 04: Mine conversations for content ideas")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", help="Text file or CSV of conversation notes")
    group.add_argument("--text", help="Paste conversation text directly")

    parser.add_argument("--field", default="notes", help="Column name if input is CSV (default: notes)")
    parser.add_argument("--output", help="Save report to file (default: print to stdout)")
    args = parser.parse_args()

    if not os.environ.get("MINIMAX_API_KEY"):
        print("Error: MINIMAX_API_KEY not set")
        sys.exit(1)

    if args.text:
        conversation_text = args.text
        source = "inline text"
    else:
        path = Path(args.input)
        if path.suffix.lower() == ".csv":
            import csv
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            texts = [r.get(args.field, "") for r in rows if r.get(args.field)]
            conversation_text = "\n\n---\n\n".join(texts)
            source = f"{path.name} ({len(texts)} conversations)"
        else:
            conversation_text = path.read_text(encoding="utf-8")
            source = path.name

    print(f"Mining content ideas from: {source}...")
    result = mine_text(conversation_text)
    report = format_output(result, source)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report saved → {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
