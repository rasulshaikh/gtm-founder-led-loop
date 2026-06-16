#!/usr/bin/env python3
"""
Phase 02: Score and Route
Scores enriched engagers 0-100 and routes them into tiers:
  Tier 1 — Hot  (80+): Direct pipeline outreach. Founder sends personally.
  Tier 2 — Warm (50-79): Email sequence + LinkedIn DM.
  Tier 3 — Nurture (<50): Content retarget. No cold outreach yet.

Usage:
    python loop/02_score_and_route.py --input enriched_engagers.csv --output scored.csv
    python loop/02_score_and_route.py --input enriched_engagers.csv --icp "B2B SaaS 50-500 employees Series A-C US/Canada"
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
import requests


MINIMAX_API_URL = "https://api.minimaxi.chat/v1/chat/completions"

# --- ICP defaults (edit for your market) ---
ICP_INDUSTRIES = ["saas", "software", "fintech", "marketplace", "b2b tech", "devtools"]
ICP_TITLES = ["vp", "head of", "director", "chief", "cro", "cmo", "cto", "founder", "owner", "gm"]
ICP_EMPLOYEE_RANGE = (20, 2000)
ICP_COUNTRIES = ["us", "usa", "united states", "canada", "uk", "united kingdom", "australia"]

SCORE_WEIGHTS = {
    "engagement": 30,    # max 30 — how they interacted with content
    "icp_role": 25,      # max 25 — job title ICP fit
    "icp_industry": 20,  # max 20 — industry fit
    "icp_size": 15,      # max 15 — company size fit
    "icp_geo": 10,       # max 10 — geography fit
}

OUTPUT_FIELDS = [
    "full_name", "first_name", "company", "title", "email", "linkedin_url",
    "industry", "employees", "website", "engagement_type", "engagement_score",
    "post_url", "post_topic", "icp_score", "tier", "tier_label",
    "score_breakdown", "recommended_play", "enriched_at",
]


def score_engagement(engagement_type: str, engagement_score: int) -> int:
    """Score 0-30 based on engagement type and warmth."""
    raw = int(engagement_score or 0)
    if raw >= 15:
        return 30
    if raw >= 10:
        return 22
    if raw >= 7:
        return 15
    return 8


def score_role(title: str) -> int:
    """Score 0-25 based on job title ICP match."""
    t = title.lower()
    if any(kw in t for kw in ["cro", "chief revenue", "vp sales", "vp of sales", "head of sales"]):
        return 25
    if any(kw in t for kw in ["cmo", "vp marketing", "head of growth", "head of marketing"]):
        return 22
    if any(kw in t for kw in ["founder", "ceo", "owner", "co-founder"]):
        return 20
    if any(kw in t for kw in ["director", "head of", "vp", "vice president"]):
        return 16
    if any(kw in t for kw in ["manager", "lead", "senior"]):
        return 8
    return 3


def score_industry(industry: str) -> int:
    """Score 0-20 based on industry ICP match."""
    ind = industry.lower()
    if any(kw in ind for kw in ICP_INDUSTRIES):
        return 20
    if "tech" in ind or "software" in ind or "digital" in ind:
        return 12
    return 3


def score_size(employees: str) -> int:
    """Score 0-15 based on employee count ICP match."""
    try:
        emp = int(str(employees).replace(",", "").split("-")[0].strip())
    except (ValueError, AttributeError):
        return 5  # unknown — give partial credit

    lo, hi = ICP_EMPLOYEE_RANGE
    if lo <= emp <= hi:
        return 15
    if emp < lo and emp >= 10:
        return 8
    if hi < emp <= hi * 3:
        return 10
    return 2


def score_geo(company: str, website: str) -> int:
    """Score 0-10 based on geography signals (rough heuristic)."""
    combined = (company + " " + website).lower()
    if any(g in combined for g in [".com", "us", "usa"]):
        return 10
    if any(g in combined for g in [".co.uk", ".com.au", ".ca", "canada", "uk", "australia"]):
        return 8
    return 3


def route_tier(score: int) -> tuple[int, str, str]:
    """Route to tier based on composite score."""
    if score >= 80:
        return 1, "Hot", "Direct outreach — founder sends personally within 24h. Reference their specific comment/engagement."
    if score >= 50:
        return 2, "Warm", "Email sequence + LinkedIn DM. Use warm cadence referencing their content engagement."
    return 3, "Nurture", "Add to content retarget audience. No cold outreach. Engage with their posts first."


def score_row(row: dict) -> dict:
    """Score a single engager and add tier routing."""
    e_score = score_engagement(row.get("engagement_type", ""), row.get("engagement_score", 0))
    r_score = score_role(row.get("title", ""))
    i_score = score_industry(row.get("industry", ""))
    s_score = score_size(row.get("employees", ""))
    g_score = score_geo(row.get("company", ""), row.get("website", ""))

    total = e_score + r_score + i_score + s_score + g_score
    tier_num, tier_label, play = route_tier(total)

    row["icp_score"] = total
    row["tier"] = tier_num
    row["tier_label"] = tier_label
    row["recommended_play"] = play
    row["score_breakdown"] = (
        f"engagement:{e_score} role:{r_score} industry:{i_score} "
        f"size:{s_score} geo:{g_score}"
    )
    return row


def run(input_csv: str, output_csv: str) -> None:
    """Score and route all engagers."""
    with open(input_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Scoring {len(rows)} engagers...")
    scored = [score_row(dict(r)) for r in rows]
    scored.sort(key=lambda r: int(r.get("icp_score") or 0), reverse=True)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(scored)

    hot = sum(1 for r in scored if r.get("tier") == 1)
    warm = sum(1 for r in scored if r.get("tier") == 2)
    nurture = sum(1 for r in scored if r.get("tier") == 3)

    print(f"\nDone. {len(scored)} engagers scored → {output_csv}")
    print(f"Tier 1 Hot:    {hot}  → Direct founder outreach")
    print(f"Tier 2 Warm:   {warm} → Email + DM sequence")
    print(f"Tier 3 Nurture:{nurture} → Content retarget only")

    # Print top 5
    print("\nTop 5 engagers:")
    for r in scored[:5]:
        print(f"  {r['full_name']} @ {r['company']} ({r['title']}) — Score: {r['icp_score']} | {r['tier_label']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 02: Score and Route engagers into tiers")
    parser.add_argument("--input", required=True, help="Enriched engagers CSV from Phase 01")
    parser.add_argument("--output", default="scored_engagers.csv")
    args = parser.parse_args()
    run(args.input, args.output)


if __name__ == "__main__":
    main()
